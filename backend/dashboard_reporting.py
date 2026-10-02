"""Read-only dashboard payloads; counting stays in the existing module services."""
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from .models import Faculty, Publication
from .publication_reporting import publication_query
from .patent_services import selected_patents, patent_kpis, patent_person_kpis, patent_drilldown, patent_type_counts
from .book_services import selected_books, book_kpis, person_kpis, participants
from .reporting import validate_date_range, within
from .research_overview import UNAVAILABLE


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
    claimed = lambda p: any(a.faculty_id == identity and a.is_claiming_faculty for a in p.authors)
    return {'faculty': {'id': identity, 'name': person.name, 'employee_id': person.employee_id, 'designation': person.designation},
            'from_date': start, 'to_date': end,
            'summary': {'journal': sum(p.publication_type == 'JOURNAL' for p in publications), 'conference': sum(p.publication_type == 'CONFERENCE' for p in publications),
                        'publications_claimed': sum(claimed(p) for p in publications), 'publications_authored': len(publications), 'patents': patent_row['invented'], 'patents_claimed': patent_row['claimed'], 'books': len(books), **{key: None for key in UNAVAILABLE}},
            'publications': [{'id': p.id, 'title': p.title, 'publication_type': p.publication_type, 'publication_date': p.publication_date, 'claimed': claimed(p), 'indexing': p.indexing, 'quartile': p.quartile, 'classification': p.classification} for p in publications],
            'patents': [{'id': p.id, 'title': p.title, 'patent_type': p.patent_type, 'application_number': p.application_number, 'filing_date': p.filing_date, 'publication_date': p.publication_date, 'grant_date': p.grant_date, 'claimed': any(i.faculty_id == identity and i.is_claiming_faculty for i in p.inventors)} for p in event_patents],
            'books': [{'id': b.id, 'title': b.title, 'work_type': b.work_type, 'publication_date': b.publication_date, 'claimed': any(c.faculty_id == identity and c.is_claiming_faculty for c in b.contributors)} for b in books], 'unavailable_modules': UNAVAILABLE}
