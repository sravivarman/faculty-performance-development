"""Read-only dashboard payloads; counting stays in the existing module services."""
from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from .models import Certification, Faculty, FdpActivity, FdpParticipant, FundingProject, FundingProjectFaculty, Publication
from .publication_reporting import publication_query
from .patent_services import selected_patents, patent_kpis, patent_person_kpis, patent_drilldown, patent_type_counts
from .book_services import selected_books, book_kpis, person_kpis, participants
from .reporting import validate_date_range, within
from .research_overview import UNAVAILABLE


FDP_ROLE_ORDER = {"ATTENDEE": 0, "RESOURCE_PERSON": 1, "COORDINATOR": 2}
FUNDING_CATEGORIES = ("SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT")
AWARDED_FUNDING_STATUSES = {"SANCTIONED", "ONGOING", "COMPLETED"}


def summed_amount(records, field):
    """Preserve the distinction between an omitted amount and a confirmed zero."""
    values = [getattr(record, field) for record in records if getattr(record, field) is not None]
    return sum(values, Decimal("0")) if values else None


def faculty_funding_summary(records):
    """Aggregate distinct project records already scoped to one Faculty Master ID."""
    awarded = [record for record in records if record.status in AWARDED_FUNDING_STATUSES]
    return {
        "projects": len(records),
        "submitted_under_review": sum(record.status in {"SUBMITTED", "UNDER_REVIEW"} for record in records),
        "awarded": len(awarded),
        "proposed_amount": summed_amount(records, "proposed_amount"),
        "sanctioned_amount": summed_amount(awarded, "sanctioned_amount"),
        "contract_amount": summed_amount(awarded, "contract_amount"),
        "amount_received": summed_amount(awarded, "amount_received"),
        "amount_utilized": summed_amount(awarded, "amount_utilized"),
    }


def monthly_trend(records, start, end, fields):
    """One shared backend month calendar, including zero and partial months."""
    validate_date_range(start, end)
    result = []
    cursor = start.replace(day=1)
    while cursor <= end:
        following = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        first, last = max(start, cursor), min(end, following - timedelta(days=1))
        result.append({'month': cursor.strftime('%Y-%m'), 'from_date': first, 'to_date': last,
                       **{key: len({r.id for r in records if eligible(r) and within(getattr(r, field), first, last)}) for key, (field, eligible) in fields.items()}})
        cursor = following
    return result


def patents_dashboard(db, start, end, filters):
    validate_date_range(start, end)
    records = selected_patents(db, **filters)
    counts = patent_kpis(records, start, end)
    return {'totals': counts, 'types': patent_type_counts(records,start,end), 'faculty': patent_person_kpis(db, records, start, end, 'faculty'),
            'trend': monthly_trend(records, start, end, {key: (field, lambda p: True) for key, field in [('filed','filing_date'), ('published','publication_date'), ('granted','grant_date')]})}


def books_dashboard(db, start, end, filters):
    validate_date_range(start, end)
    records = selected_books(db, from_date=start, to_date=end, **filters)
    counts = book_kpis(records)
    classification = {key.lower(): sum(r.classification == key if key != 'UNKNOWN' else r.classification in (None, 'UNKNOWN') for r in records) for key in ('INTERNATIONAL', 'NATIONAL', 'OTHER', 'UNKNOWN')}
    counts.update(international=classification['international'], national=classification['national'], faculty_contributors=len({c.faculty_id for r in records for c in participants(r, 'FACULTY') if c.faculty_id}))
    return {'totals': counts, 'classification': classification, 'faculty': person_kpis(db, records, 'faculty'), 'classification_configured': True,
            'trend': monthly_trend(records, start, end, {'books': ('publication_date', lambda r: r.work_type == 'BOOK'), 'chapters': ('publication_date', lambda r: r.work_type == 'BOOK_CHAPTER')})}


def faculty_details(db, identity, start, end):
    validate_date_range(start, end)
    person = db.get(Faculty, identity)
    if not person:
        raise HTTPException(404, 'Faculty not found')
    publications = db.scalars(publication_query(from_date=start, to_date=end, dashboard_only=True, faculty_id=identity).order_by(Publication.publication_date.desc())).all()
    patents = selected_patents(db, faculty_id=identity)
    patent_counts = patent_person_kpis(db, patents, start, end, 'faculty')
    patent_row = next(row for row in patent_counts if row['id'] == identity)
    event_patents = [p for p in patents if any(within(getattr(p, field), start, end) for field in ('filing_date', 'publication_date', 'grant_date'))]
    books = selected_books(db, from_date=start, to_date=end, faculty_id=identity)
    fdp = db.scalars(select(FdpActivity).where(FdpActivity.is_active.is_(True), FdpActivity.start_date.between(start,end), FdpActivity.participants.any(FdpParticipant.faculty_id==identity))).all()
    funding_date = func.coalesce(FundingProject.sanction_date, FundingProject.proposal_submission_date, FundingProject.start_date)
    funding_projects = db.scalars(select(FundingProject).where(
        FundingProject.is_active.is_(True),
        funding_date.between(start, end),
        FundingProject.faculty.any(FundingProjectFaculty.faculty_id == identity),
    )).all()
    certifications = db.scalars(select(Certification).where(
        Certification.is_active.is_(True),
        Certification.faculty_id==identity,
        or_(
            and_(Certification.status=="COMPLETED", Certification.completion_date.between(start,end)),
            Certification.status=="IN_PROGRESS",
        ),
    )).all()
    funding_by_category = {
        category: [record for record in funding_projects if record.category == category]
        for category in FUNDING_CATEGORIES
    }
    funding_summary = {
        "sponsored_research": faculty_funding_summary(funding_by_category["SPONSORED_RESEARCH"]),
        "consultancy": faculty_funding_summary(funding_by_category["CONSULTANCY"]),
        "internal_grants": faculty_funding_summary(funding_by_category["INTERNAL_GRANT"]),
    }
    claimed = lambda p: any(a.faculty_id == identity and a.is_claiming_faculty for a in p.authors)
    def activity_roles(activity):
        return sorted(
            {participant.role for participant in activity.participants if participant.faculty_id == identity},
            key=lambda role: (FDP_ROLE_ORDER.get(role, len(FDP_ROLE_ORDER)), role),
        )

    def funding_roles(record):
        return [member for member in sorted(record.faculty, key=lambda member: (member.display_order, member.id)) if member.faculty_id == identity]

    return {'faculty': {'id': identity, 'name': person.name, 'employee_id': person.employee_id, 'designation': person.designation},
            'from_date': start, 'to_date': end,
            'summary': {'journal': sum(p.publication_type == 'JOURNAL' for p in publications), 'conference': sum(p.publication_type == 'CONFERENCE' for p in publications),
                        'publications_claimed': sum(claimed(p) for p in publications), 'publications_authored': len(publications), 'patents': patent_row['invented'], 'patents_claimed': patent_row['claimed'], 'books': len(books), 'fdp':len(fdp),
                        # `certifications` and `funding_projects` remain for existing API consumers.
                        'certifications':len(certifications), 'certifications_completed': sum(item.status == 'COMPLETED' for item in certifications), 'certifications_in_progress': sum(item.status == 'IN_PROGRESS' for item in certifications),
                        'funding_projects': len(funding_projects), 'sponsored_research': len(funding_by_category['SPONSORED_RESEARCH']),
                        'proposals': len(funding_by_category['SPONSORED_RESEARCH']), 'consultancy': len(funding_by_category['CONSULTANCY']),
                        'internal_grants': len(funding_by_category['INTERNAL_GRANT']), **{key: None for key in UNAVAILABLE}},
            'publications': [{'id': p.id, 'title': p.title, 'publication_type': p.publication_type, 'publication_date': p.publication_date, 'claimed': claimed(p), 'indexing': p.indexing, 'quartile': p.quartile, 'classification': p.classification} for p in publications],
            'patents': [{'id': p.id, 'title': p.title, 'patent_type': p.patent_type, 'application_number': p.application_number, 'filing_date': p.filing_date, 'publication_date': p.publication_date, 'grant_date': p.grant_date, 'claimed': any(i.faculty_id == identity and i.is_claiming_faculty for i in p.inventors)} for p in event_patents],
            'books': [{'id': b.id, 'title': b.title, 'work_type': b.work_type, 'publication_date': b.publication_date, 'claimed': any(c.faculty_id == identity and c.is_claiming_faculty for c in b.contributors)} for b in books],
            'fdp': [{'id':x.id, 'title':x.title, 'activity_type':x.activity_type, 'organizing_institution':x.organizing_institution,
                     'publication_date':x.start_date, 'start_date':x.start_date, 'end_date':x.end_date, 'duration_value':x.duration_value,
                     'duration_unit':x.duration_unit, 'is_active':x.is_active, 'roles':activity_roles(x),
                     # Retain the original singular field for existing consumers.
                     'role':activity_roles(x)[0] if activity_roles(x) else None} for x in fdp],
            'certifications': [{'id':x.id, 'title':x.name, 'publication_date':x.completion_date, 'completion_date':x.completion_date,
                                'issue_date':x.issue_date, 'expiry_date':x.expiry_date, 'credential_id':x.credential_id,
                                'category':x.category, 'provider':x.provider, 'status':x.status, 'is_active':x.is_active} for x in certifications],
            'funding_projects': [{'id': x.id, 'title': x.title, 'publication_date': x.sanction_date or x.proposal_submission_date or x.start_date,
                                  'reporting_date':x.sanction_date or x.proposal_submission_date or x.start_date, 'category': x.category,
                                  'funding_agency':x.funding_agency, 'status': x.status, 'start_date':x.start_date, 'end_date':x.end_date,
                                  'proposed_amount':x.proposed_amount, 'sanctioned_amount':x.sanctioned_amount, 'contract_amount':x.contract_amount,
                                  'amount_received':x.amount_received, 'amount_utilized':x.amount_utilized, 'currency':x.currency,
                                  'roles': [member.agency_role_label or member.role for member in funding_roles(x)],
                                  'investigator_roles': [{'role':member.role, 'agency_role_label':member.agency_role_label} for member in funding_roles(x)]} for x in funding_projects],
            'funding_summary': funding_summary,
            'unavailable_modules': UNAVAILABLE}
