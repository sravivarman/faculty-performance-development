"""Shared SQL predicates and distinct, read-only publication dashboard aggregates."""
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select, func, case, or_, and_, exists, Text

from .models import Publication as P, PublicationAuthor as A, Faculty
from .reporting import validate_date_range

TAGS = ['SCI', 'SCIE', 'SCOPUS', 'WEB_OF_SCIENCE', 'ESCI', 'UGC_CARE', 'OTHER', 'NONE', 'UNKNOWN']
QUARTILES = ['Q1', 'Q2', 'Q3', 'Q4', 'NOT_APPLICABLE', 'UNKNOWN']
SCOPES = ['INTERNATIONAL', 'NATIONAL', 'OTHER', 'UNKNOWN']


def tag(value):
    values = func.json_each(P.indexing).table_valued('value').alias()
    present = exists(select(1).select_from(values).where(values.c.value == value))
    return or_(present, func.json_array_length(P.indexing) == 0) if value == 'UNKNOWN' else present


def student():
    return P.authors.any(and_(A.person_type == 'STUDENT', A.student_id.is_not(None)))


def internal_unknown():
    # Affiliation is a source JSON array; only UNKNOWN author records are counted.
    return and_(A.person_type == 'UNKNOWN', func.lower(func.cast(A.affiliation_from_source, Text)).like('%vardhaman%'))


def metric_condition(metric, faculty=None):
    claimant = and_(A.person_type == 'FACULTY', A.is_claiming_faculty.is_(True))
    if faculty:
        claimant = and_(claimant, A.faculty_id == faculty)
    conditions = {
        'total': P.id.is_not(None), 'authored': P.id.is_not(None),
        'journal': P.publication_type == 'JOURNAL', 'conference': P.publication_type == 'CONFERENCE',
        'claimed': P.authors.any(claimant), 'faculty_claimants': P.authors.any(claimant),
        'unique_faculty': P.authors.any(A.faculty_id.is_not(None)),
        'unique_students': student(), 'with_students': student(), 'without_students': ~student(),
        'indexed': or_(*[tag(t) for t in TAGS if t not in ('NONE', 'UNKNOWN')]),
        'sci_scie': or_(tag('SCI'), tag('SCIE')),
        'missing_claimant': ~P.authors.any(and_(A.person_type == 'FACULTY', A.is_claiming_faculty.is_(True))),
        'missing_evidence': ~P.evidence.any(),
        'internal_unknown': P.authors.any(internal_unknown()),
        **{t.lower(): tag(t) for t in TAGS},
        **{q.lower(): (or_(P.quartile.is_(None), P.quartile == 'UNKNOWN') if q == 'UNKNOWN' else P.quartile == q) for q in QUARTILES},
        **{s.lower(): P.classification == s for s in SCOPES},
        'indexing_unknown': tag('UNKNOWN'), 'classification_unknown': P.classification == 'UNKNOWN',
        'indexing_other': tag('OTHER'),
        'quartile_unknown': or_(P.quartile.is_(None), P.quartile == 'UNKNOWN'),
    }
    for kind in ('journal', 'conference'):
        for role in ('claimed', 'authored'):
            author = A.faculty_id == faculty if faculty else A.faculty_id.is_not(None)
            conditions[f'{kind}_{role}'] = and_(P.publication_type == kind.upper(), P.authors.any(and_(author, A.is_claiming_faculty.is_(True)) if role == 'claimed' else author))
        for scope in ('international', 'national'):
            conditions[f'{scope}_{kind}'] = and_(P.classification == scope.upper(), P.publication_type == kind.upper())
    if metric not in conditions:
        raise HTTPException(422, 'Unknown KPI metric')
    return conditions[metric]


def publication_query(**filters):
    query = select(P)
    if filters.get('dashboard_only'): query = query.where(P.publication_type.in_(['JOURNAL', 'CONFERENCE']))
    if not filters.get('include_inactive'):
        query = query.where(P.is_active.is_(True))
    bounds = validate_date_range(filters.get('from_date'), filters.get('to_date'), required=False)
    if bounds:
        query = query.where(P.publication_date.between(*bounds))
    for key, column in [('publication_type', P.publication_type), ('classification', P.classification)]:
        if filters.get(key): query = query.where(column == filters[key])
    if filters.get('quartile'):
        query = query.where(metric_condition(filters['quartile'].lower()))
    for key, column in [('faculty_id', A.faculty_id), ('drill_faculty_id', A.faculty_id), ('student_id', A.student_id), ('drill_student_id', A.student_id)]:
        if filters.get(key): query = query.where(P.authors.any(column == filters[key]))
    if filters.get('claiming_faculty_id'):
        query = query.where(P.authors.any(and_(A.faculty_id == filters['claiming_faculty_id'], A.is_claiming_faculty.is_(True))))
    if filters.get('student_participation') is not None:
        query = query.where(student() if filters['student_participation'] else ~student())
    if filters.get('indexing'): query = query.where(tag(filters['indexing']))
    if filters.get('metric'): query = query.where(metric_condition(filters['metric'], filters.get('drill_faculty_id') or filters.get('faculty_id')))
    return query


def dashboard(db, filters):
    bounds = validate_date_range(filters['from_date'], filters['to_date'])
    selected = dict(filters, metric=None, drill_faculty_id=None, drill_student_id=None)
    # The executive dashboard covers Journal + Conference; legacy Other records remain available in the registry.
    ids = publication_query(**selected).where(P.publication_type.in_(['JOURNAL', 'CONFERENCE'])).with_only_columns(P.id).subquery()
    base = P.id.in_(select(ids.c.id))
    def count(condition):
        return func.count(func.distinct(case((condition, P.id))))
    metrics = list(dict.fromkeys(['total', 'journal', 'conference', 'with_students', 'indexed', 'sci_scie'] + [t.lower() for t in TAGS if t not in ('OTHER', 'UNKNOWN')] + ['indexing_other', 'q1', 'q2', 'q3', 'q4', 'not_applicable', 'quartile_unknown'] + ['international', 'national', 'other', 'classification_unknown', 'missing_claimant', 'missing_evidence', 'indexing_unknown', 'internal_unknown']))
    totals = dict(db.execute(select(*[count(metric_condition(m)).label(m) for m in metrics]).where(base)).mappings().one())
    # Distinct people and author-record warnings are intentionally different units.
    totals['faculty_claimants'] = db.scalar(select(func.count(func.distinct(A.faculty_id))).where(A.publication_id.in_(select(ids.c.id)), A.is_claiming_faculty.is_(True), A.person_type == 'FACULTY'))
    totals['unique_students'] = db.scalar(select(func.count(func.distinct(A.student_id))).where(A.publication_id.in_(select(ids.c.id)), A.person_type == 'STUDENT'))
    totals['unclassified_internal_authors'] = db.scalar(select(func.count(A.id)).where(A.publication_id.in_(select(ids.c.id)), internal_unknown()))
    authored = and_(A.faculty_id == Faculty.id, A.person_type == 'FACULTY')
    faculty_metrics = {
        'claimed': A.is_claiming_faculty.is_(True), 'authored': P.id.is_not(None),
        'journal_claimed': and_(A.is_claiming_faculty.is_(True), P.publication_type == 'JOURNAL'),
        'conference_claimed': and_(A.is_claiming_faculty.is_(True), P.publication_type == 'CONFERENCE'),
        'scopus': tag('SCOPUS'), 'sci_scie': or_(tag('SCI'), tag('SCIE')),
        'q1': P.quartile == 'Q1', 'q2': P.quartile == 'Q2', 'with_students': student(),
    }
    faculty = [dict(row) for row in db.execute(select(Faculty.id, Faculty.name, *[count(c).label(k) for k, c in faculty_metrics.items()]).select_from(Faculty).outerjoin(A, authored).outerjoin(P, and_(P.id == A.publication_id, base)).group_by(Faculty.id).order_by(Faculty.name)).mappings()]
    month = func.strftime('%Y-%m', P.publication_date)
    monthly = {r['month']: dict(r) for r in db.execute(select(month.label('month'), count(P.id.is_not(None)).label('total'), count(P.publication_type == 'JOURNAL').label('journal'), count(P.publication_type == 'CONFERENCE').label('conference')).where(base).group_by(month)).mappings()}
    trend = []
    cursor = bounds[0].replace(day=1)
    while cursor <= bounds[1]:
        key = cursor.strftime('%Y-%m')
        following = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        trend.append({**monthly.get(key, {'month': key, 'total': 0, 'journal': 0, 'conference': 0}), 'from_date': max(cursor, bounds[0]), 'to_date': min(following - timedelta(days=1), bounds[1])})
        cursor = following
    claimant = select(Faculty.name).join(A, A.faculty_id == Faculty.id).where(A.publication_id == P.id, A.is_claiming_faculty.is_(True)).correlate(P).scalar_subquery()
    recent_rows = [dict(row) for row in db.execute(select(P.id, P.title, P.publication_date, P.publication_type, claimant.label('claimant'), P.indexing, P.classification, P.quartile).where(base).order_by(P.publication_date.desc(), P.id.desc()).limit(5)).mappings()]
    return {'totals': totals, 'faculty': faculty, 'trend': trend, 'recent': recent_rows}
