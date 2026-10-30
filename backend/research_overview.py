"""Read-only cross-module reporting; module services own their counting rules."""
from datetime import date, timedelta
from sqlalchemy import select, func, and_, or_, Integer, union_all
from fastapi import HTTPException
from .models import Publication, PublicationAuthor, Faculty, Patent, PatentInventor, BookPublication, BookContributor, Certification, FdpActivity, FdpParticipant
from .publication_reporting import dashboard as publication_dashboard, publication_query
from .patent_services import selected_patents, patent_kpis, patent_person_kpis, patent_drilldown, patent_type_counts
from .book_services import selected_books, book_kpis, person_kpis, participants
from .funding_api import funding_dashboard_data, project_filters
from .reporting import validate_date_range, within

# Kept in the response for compatibility with the trend chart contract.  All
# currently supported home-dashboard modules now provide live data.
UNAVAILABLE = {}


def activity_trend(db, start, end, calendar_year=None, granularity='MONTHLY'):
    """Compact SQL aggregates only; preserve publication, filing and book dates.

    Calendar selection intersects the global inclusive range. Year availability
    comes from all eligible history, never from created_at or the browser.
    """
    validate_date_range(start, end)
    if granularity not in ('MONTHLY', 'QUARTERLY', 'HALF_YEARLY', 'YEARLY'):
        raise HTTPException(422, 'Invalid trend granularity')
    if calendar_year is not None and not 1 <= calendar_year <= 9999:
        raise HTTPException(422, 'Invalid calendar year')
    pub = publication_query(dashboard_only=True).with_only_columns(Publication.id).subquery()
    patent_eligible = and_(Patent.is_active.is_(True), Patent.inventors.any(PatentInventor.institution_scope == "CURRENT_DEPARTMENT"))
    patent_events = union_all(*(select(Patent.id.label("id"), field.label("event_date")).where(patent_eligible, field.is_not(None)) for field in (Patent.filing_date, Patent.publication_date, Patent.grant_date))).subquery()
    sources = [
        ('journal', Publication.id, Publication.publication_date, and_(Publication.id.in_(select(pub.c.id)), Publication.publication_type == 'JOURNAL')),
        ('conference', Publication.id, Publication.publication_date, and_(Publication.id.in_(select(pub.c.id)), Publication.publication_type == 'CONFERENCE')),
        ('patents', patent_events.c.id, patent_events.c.event_date, True),
        ('books', BookPublication.id, BookPublication.publication_date, and_(BookPublication.is_active.is_(True), BookPublication.contributors.any(and_(BookContributor.institution_scope == 'CURRENT_DEPARTMENT', or_(BookPublication.work_type == 'BOOK', BookContributor.role == 'AUTHOR'))))),
    ]
    years = set()
    for _, identity, business_date, eligible in sources:
        years.update(int(y) for y in db.scalars(select(func.distinct(func.strftime('%Y', business_date))).where(eligible, business_date.is_not(None))))
    available = sorted(years, reverse=True)
    current = date.today().year
    year = calendar_year or (current if current in years else available[0] if available else current)
    keys = [str(y) for y in sorted(years)] if granularity == 'YEARLY' else ([str(i) for i in range(1, 13)] if granularity == 'MONTHLY' else ['1', '2', '3', '4'] if granularity == 'QUARTERLY' else ['1', '2'])
    labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'] if granularity == 'MONTHLY' else [f'Q{i}' for i in range(1,5)] if granularity == 'QUARTERLY' else ['H1','H2'] if granularity == 'HALF_YEARLY' else keys
    buckets = {key: {'label': label, **{name: 0 for name, *_ in sources}, **{name: None for name in UNAVAILABLE}} for key, label in zip(keys, labels)}
    for name, identity, business_date, eligible in sources:
        month = func.cast(func.strftime('%m', business_date), Integer)
        group = func.strftime('%Y', business_date) if granularity == 'YEARLY' else month if granularity == 'MONTHLY' else func.cast((month - 1) / (3 if granularity == 'QUARTERLY' else 6), Integer) + 1
        query = select(group, func.count(func.distinct(identity))).where(eligible, business_date.between(start, end))
        if granularity != 'YEARLY':
            query = query.where(func.strftime('%Y', business_date) == f'{year:04d}')
        for key, count in db.execute(query.group_by(group)):
            if str(key) in buckets:
                buckets[str(key)][name] = count
    return {'available_years': available, 'calendar_year': year, 'granularity': granularity, 'series': {**{'journal':'Journals','conference':'Conferences','patents':'Patents','books':'Books / Chapters'}, **UNAVAILABLE}, 'unavailable_modules': UNAVAILABLE, 'buckets': list(buckets.values())}


def activities(db, start, end):
    """Minimal record summaries; never substitute created_at for an activity date."""
    rows = []
    faculty_names = dict(db.execute(select(Faculty.id, Faculty.name)).all())
    pubs = publication_query(from_date=start, to_date=end, dashboard_only=True).with_only_columns(Publication.id, Publication.title, Publication.publication_date, Publication.publication_type, func.group_concat(func.distinct(PublicationAuthor.faculty_id)).label('faculty_ids'), func.group_concat(func.distinct(PublicationAuthor.student_id)).label('student_ids')).outerjoin(PublicationAuthor, PublicationAuthor.publication_id == Publication.id).group_by(Publication.id)
    for p in db.execute(pubs).mappings():
        rows.append({'date': p['publication_date'], 'module': 'publications', 'id': p['id'], 'title': p['title'], 'status': p['publication_type'], 'faculty_ids': sorted(map(int, p['faculty_ids'].split(','))) if p['faculty_ids'] else [], 'student_ids': sorted(map(int, p['student_ids'].split(','))) if p['student_ids'] else []})
    patents = selected_patents(db)
    for p in patents:
        events = [(getattr(p, field), name) for field, name in [('filing_date', 'Filed'), ('publication_date', 'Published'), ('grant_date', 'Granted')] if within(getattr(p, field), start, end)]
        if events:
            latest, outcome = max(events)
            rows.append({'date': latest, 'module': 'patents', 'id': p.id, 'title': p.title, 'status': outcome, 'faculty_ids': sorted({i.faculty_id for i in p.inventors if i.is_current_department and i.faculty_id}), 'student_ids': sorted({i.student_id for i in p.inventors if i.is_current_department and i.student_id})})
    books = selected_books(db, from_date=start, to_date=end)
    for b in books:
        rows.append({'date': b.publication_date, 'module': 'books', 'id': b.id, 'title': b.title, 'status': b.work_type, 'faculty_ids': sorted({c.faculty_id for c in participants(b, 'FACULTY') if c.faculty_id}), 'student_ids': sorted({c.student_id for c in participants(b, 'STUDENT') if c.student_id})})
    for row in rows:
        row['faculty'] = ', '.join(faculty_names[i] for i in row['faculty_ids']) or 'No confirmed faculty author/inventor'
    return sorted(rows, key=lambda r: (r['date'], r['module'], r['id']), reverse=True), patents, books


def overview(db, start, end):
    validate_date_range(start, end)
    publication = publication_dashboard(db, {'from_date': start, 'to_date': end})
    rows, patents, books = activities(db, start, end)
    fdp = db.scalars(select(FdpActivity).where(FdpActivity.is_active.is_(True), FdpActivity.start_date.between(start, end))).all()
    certifications = db.scalars(select(Certification).where(
        Certification.is_active.is_(True),
        Certification.status == 'COMPLETED',
        Certification.completion_date.between(start, end),
    )).all()
    in_progress_certifications = db.scalars(select(Certification).where(
        Certification.is_active.is_(True), Certification.status == 'IN_PROGRESS',
    )).all()
    funding = {
        category: funding_dashboard_data(db, project_filters(category=category), start, end)
        for category in ('SPONSORED_RESEARCH', 'CONSULTANCY', 'INTERNAL_GRANT')
    }
    sponsored, consultancy, internal_grants = (
        funding['SPONSORED_RESEARCH'], funding['CONSULTANCY'], funding['INTERNAL_GRANT']
    )
    patent = patent_kpis(patents, start, end)
    patent['with_students'] = len(patent_drilldown(patents, start, end, 'with_confirmed_students'))
    patent_faculty = {p['id']: p for p in patent_person_kpis(db, patents, start, end, 'faculty')}
    book_faculty = {b['id']: b for b in person_kpis(db, books, 'faculty')}
    faculty = []
    publication_types = {}
    type_query = publication_query(from_date=start, to_date=end, dashboard_only=True).with_only_columns(PublicationAuthor.faculty_id, Publication.publication_type, func.count(func.distinct(Publication.id))).join(PublicationAuthor).where(PublicationAuthor.person_type == 'FACULTY').group_by(PublicationAuthor.faculty_id, Publication.publication_type)
    for identity, kind, count in db.execute(type_query):
        publication_types[(identity, kind)] = count
    funding_faculty = {
        category: {person['id']: person['projects'] for person in report['faculty']}
        for category, report in funding.items()
    }
    fdp_faculty = {
        identity for activity in fdp for identity in {member.faculty_id for member in activity.participants if member.faculty_id}
    }
    certification_faculty = {item.faculty_id for item in certifications}
    in_progress_faculty = {item.faculty_id for item in in_progress_certifications}
    for p in publication['faculty']:
        identity = p['id']
        fdp_count = sum(any(x.faculty_id == identity for x in item.participants) for item in fdp)
        completed_certification_count = sum(item.faculty_id == identity for item in certifications)
        in_progress_certification_count = sum(item.faculty_id == identity for item in in_progress_certifications)
        sponsored_count = funding_faculty['SPONSORED_RESEARCH'].get(identity, 0)
        consultancy_count = funding_faculty['CONSULTANCY'].get(identity, 0)
        internal_grant_count = funding_faculty['INTERNAL_GRANT'].get(identity, 0)
        faculty.append({'id': identity, 'name': p['name'], 'publications_claimed': p['claimed'], 'publications_authored': p['authored'], 'patents_claimed': patent_faculty[identity]['claimed'], 'patents_invented': patent_faculty[identity]['invented'], 'books': book_faculty[identity]['participated'], 'fdp':sum(any(x.faculty_id==identity for x in item.participants) for item in fdp), 'certifications':sum(item.faculty_id==identity for item in certifications), **{k: None for k in UNAVAILABLE}, 'total_activities': sum(identity in r['faculty_ids'] for r in rows)})
        faculty[-1].update({
            'fdp': fdp_count,
            'certifications': completed_certification_count,
            'certifications_in_progress': in_progress_certification_count,
            # `proposals` is retained for response compatibility; the home UI
            # uses the clearer research-projects label.
            'proposals': sponsored_count,
            'research_projects': sponsored_count,
            'consultancy': consultancy_count,
            'internal_grants': internal_grant_count,
            'total_activities': sum(identity in r['faculty_ids'] for r in rows)
            + fdp_count + completed_certification_count + in_progress_certification_count
            + sponsored_count + consultancy_count + internal_grant_count,
        })
    contributors = (
        {identity for r in rows for identity in r['faculty_ids']}
        | fdp_faculty | certification_faculty | in_progress_faculty
        | {identity for report in funding_faculty.values() for identity in report}
    )
    for row in faculty:
        row['journal'] = publication_types.get((row['id'], 'JOURNAL'), 0)
        row['conference'] = publication_types.get((row['id'], 'CONFERENCE'), 0)
    students = {identity for r in rows for identity in r['student_ids']}
    trend = []
    for month in publication['trend']:
        year, number = map(int, month['month'].split('-'))
        first = max(start, date(year, number, 1))
        next_month = date(year + (number == 12), number % 12 + 1, 1)
        last = min(end, next_month - timedelta(days=1))
        trend.append({'month': month['month'], 'publications': month['total'], 'patents': len(patent_drilldown(patents, first, last)), 'books': sum(within(b.publication_date, first, last) for b in books)})
    initiated = patent_drilldown(patents, start, end)
    data_quality = {k: publication['totals'][k] for k in ['classification_unknown', 'missing_evidence', 'internal_unknown']}
    data_quality['patents_missing_evidence'] = sum(not p.evidence for p in initiated)
    data_quality['patents_missing_lifecycle'] = len(patent_drilldown(patents, start, end, 'missing_lifecycle'))
    return {
        'activity_totals': {
            'publications': publication['totals']['total'], 'patents': patent['unique'],
            'books': book_kpis(books)['total'], 'fdp': len(fdp),
            # Completed certification outcomes use their inclusive completion
            # date; current in-progress work is intentionally date-independent.
            'certifications': len(certifications),
            'certifications_in_progress': len(in_progress_certifications),
            'research_projects': sponsored['totals']['total'],
            'proposals': sponsored['totals']['total'],
            'consultancy': consultancy['totals']['total'],
            'internal_grants': internal_grants['totals']['total'],
        },
        'outcomes': {
            'journal': publication['totals']['journal'], 'conference': publication['totals']['conference'],
            'patents_granted': patent['granted'],
            'proposals_sanctioned': sponsored['totals']['sanctioned'],
            'funds_sanctioned': sponsored['totals']['sanctioned_amount'],
            'consultancy_revenue': consultancy['totals']['amount_received'],
            'faculty_contributors': len(contributors),
        },
        'publication_summary': publication['totals'], 'patent_summary': patent, 'patent_types': patent_type_counts(patents,start,end),
        'financial_summary': {
            'sponsored_proposed_amount': sponsored['totals']['proposed_amount'],
            'sponsored_sanctioned_amount': sponsored['totals']['sanctioned_amount'],
            'consultancy_contract_amount': consultancy['totals']['contract_value'],
            'consultancy_amount_received': consultancy['totals']['amount_received'],
            'internal_grants_sanctioned_amount': internal_grants['totals']['sanctioned_amount'],
            'internal_grants_amount_utilized': internal_grants['totals']['amount_utilized'],
        },
        'funding_summary': {
            'sponsored_research': sponsored['totals'],
            'consultancy': consultancy['totals'],
            'internal_grants': internal_grants['totals'],
        },
        'faculty_summary': faculty, 'faculty_participation': {'with_activity': len(contributors), 'without_activity': len(faculty) - len(contributors)},
        'student_summary': {'publications': publication['totals']['with_students'], 'patents': patent['with_students'], 'unique_contributors': len(students)},
        'trend': trend, 'recent_activity': rows[:10], 'data_quality': data_quality,
        'unavailable_modules': UNAVAILABLE,
    }
