"""Read-only dashboard payloads; counting stays in the existing module services."""
from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import and_, exists, func, or_, select
from .models import (
    BookContributor,
    BookPublication,
    Certification,
    Department,
    Faculty,
    FacultyDepartmentAffiliation,
    FdpActivity,
    FdpParticipant,
    FundingProject,
    FundingProjectFaculty,
    Patent,
    PatentInventor,
    Publication,
    PublicationAuthor,
)
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


def _faculty_department_record_predicate(parent, association, association_parent_key, date_column, identity, department_id, attribution_mode):
    """Require the selected Faculty's own contribution and affiliation.

    The shared Department predicate is intentionally record-centric: it finds a
    record with *any* eligible departmental contributor.  A Faculty profile has
    stricter intersection semantics, so this correlated predicate keeps the
    selected Faculty ID on both the contributor and affiliation checks.
    """
    affiliation_conditions = [
        FacultyDepartmentAffiliation.faculty_id == identity,
        FacultyDepartmentAffiliation.department_id == department_id,
        FacultyDepartmentAffiliation.is_primary.is_(True),
    ]
    if attribution_mode == "CURRENT":
        affiliation_conditions.append(FacultyDepartmentAffiliation.effective_to.is_(None))
    else:
        affiliation_conditions.extend([
            date_column.is_not(None),
            FacultyDepartmentAffiliation.effective_from.is_not(None),
            FacultyDepartmentAffiliation.effective_from <= date_column,
            or_(
                FacultyDepartmentAffiliation.effective_to.is_(None),
                FacultyDepartmentAffiliation.effective_to >= date_column,
            ),
        ])
    affiliation = exists(select(1).where(*affiliation_conditions).correlate(parent))
    return exists(select(1).where(
        association_parent_key == parent.id,
        association.faculty_id == identity,
        affiliation,
    ).correlate(parent))


def _current_department(person):
    current = [item for item in person.department_affiliations if item.is_primary and item.effective_to is None]
    if not current:
        return None
    affiliation = max(current, key=lambda item: (item.effective_from or date.min, item.id))
    if not affiliation.department:
        return None
    return {
        "id": affiliation.department.id,
        "code": affiliation.department.code,
        "name": affiliation.department.name,
        "is_active": affiliation.department.is_active,
    }


def _profile_context(db, identity, department_id, attribution_mode):
    if attribution_mode not in {"CURRENT", "AT_ACTIVITY_DATE"}:
        raise HTTPException(422, "attribution_mode must be CURRENT or AT_ACTIVITY_DATE")
    if department_id is None:
        return {"type": "COMPLETE_PROFILE", "department": None, "attribution_mode": attribution_mode}
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(422, "Unknown Department ID")
    return {
        "type": "DEPARTMENT_ATTRIBUTED",
        "department": {"id": department.id, "code": department.code, "name": department.name, "is_active": department.is_active},
        "attribution_mode": attribution_mode,
    }


def faculty_details(db, identity, start, end, *, department_id=None, attribution_mode="CURRENT"):
    validate_date_range(start, end)
    person = db.get(Faculty, identity)
    if not person:
        raise HTTPException(404, 'Faculty not found')
    context = _profile_context(db, identity, department_id, attribution_mode)
    publications_query = publication_query(from_date=start, to_date=end, dashboard_only=True, faculty_id=identity)
    if department_id is not None:
        publications_query = publications_query.where(_faculty_department_record_predicate(
            Publication, PublicationAuthor, PublicationAuthor.publication_id,
            Publication.publication_date, identity, department_id, attribution_mode,
        ))
    publications = db.scalars(publications_query.order_by(Publication.publication_date.desc(), Publication.id.desc())).all()

    patents_query = select(Patent).where(
        Patent.is_active.is_(True),
        Patent.inventors.any(PatentInventor.faculty_id == identity),
    )
    if department_id is not None:
        patents_query = patents_query.where(_faculty_department_record_predicate(
            Patent, PatentInventor, PatentInventor.patent_id,
            Patent.filing_date, identity, department_id, attribution_mode,
        ))
    patents = db.scalars(patents_query.order_by(Patent.filing_date.desc(), Patent.id.desc())).all()
    event_patents = [p for p in patents if any(within(getattr(p, field), start, end) for field in ('filing_date', 'publication_date', 'grant_date'))]
    patent_claimed = sum(any(i.faculty_id == identity and i.is_claiming_faculty for i in patent.inventors) for patent in event_patents)
    books_query = select(BookPublication).where(
        BookPublication.is_active.is_(True),
        BookPublication.publication_date.between(start, end),
        BookPublication.contributors.any(BookContributor.faculty_id == identity),
    )
    if department_id is not None:
        books_query = books_query.where(_faculty_department_record_predicate(
            BookPublication, BookContributor, BookContributor.book_record_id,
            BookPublication.publication_date, identity, department_id, attribution_mode,
        ))
    books = db.scalars(books_query.order_by(BookPublication.publication_date.desc(), BookPublication.id.desc())).all()

    fdp_query = select(FdpActivity).where(
        FdpActivity.is_active.is_(True), FdpActivity.start_date.between(start, end),
        FdpActivity.participants.any(FdpParticipant.faculty_id == identity),
    )
    if department_id is not None:
        fdp_query = fdp_query.where(_faculty_department_record_predicate(
            FdpActivity, FdpParticipant, FdpParticipant.activity_id,
            FdpActivity.start_date, identity, department_id, attribution_mode,
        ))
    fdp = db.scalars(fdp_query.order_by(FdpActivity.start_date.desc(), FdpActivity.id.desc())).all()
    funding_date = func.coalesce(FundingProject.sanction_date, FundingProject.proposal_submission_date, FundingProject.start_date)
    funding_query = select(FundingProject).where(
        FundingProject.is_active.is_(True),
        funding_date.between(start, end),
        FundingProject.faculty.any(FundingProjectFaculty.faculty_id == identity),
    )
    if department_id is not None:
        funding_query = funding_query.where(_faculty_department_record_predicate(
            FundingProject, FundingProjectFaculty, FundingProjectFaculty.funding_project_id,
            FundingProject.sanction_date, identity, department_id, attribution_mode,
        ))
    funding_projects = db.scalars(funding_query.order_by(FundingProject.sanction_date.desc(), FundingProject.id.desc())).all()

    certification_query = select(Certification).where(
        Certification.is_active.is_(True),
        Certification.faculty_id==identity,
        or_(
            and_(Certification.status=="COMPLETED", Certification.completion_date.between(start,end)),
            Certification.status=="IN_PROGRESS",
        ),
    )
    if department_id is not None:
        certification_affiliation = exists(select(1).where(
            FacultyDepartmentAffiliation.faculty_id == identity,
            FacultyDepartmentAffiliation.department_id == department_id,
            FacultyDepartmentAffiliation.is_primary.is_(True),
            *(
                (FacultyDepartmentAffiliation.effective_to.is_(None),)
                if attribution_mode == "CURRENT" else
                (
                    Certification.completion_date.is_not(None),
                    FacultyDepartmentAffiliation.effective_from.is_not(None),
                    FacultyDepartmentAffiliation.effective_from <= Certification.completion_date,
                    or_(FacultyDepartmentAffiliation.effective_to.is_(None), FacultyDepartmentAffiliation.effective_to >= Certification.completion_date),
                )
            ),
        ).correlate(Certification))
        # Current in-progress work has no completion date.  It can be
        # department-attributed in CURRENT mode, but deliberately remains
        # unverified in activity-date mode rather than being assigned a date.
        certification_query = certification_query.where(certification_affiliation)
    certifications = db.scalars(certification_query.order_by(Certification.completion_date.desc(), Certification.id.desc())).all()
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

    return {'faculty': {'id': identity, 'name': person.name, 'employee_id': person.employee_id, 'designation': person.designation, 'is_active': person.is_active, 'current_department': _current_department(person)},
            'from_date': start, 'to_date': end,
            'context': context,
            'breakdowns': {
                'publications': {
                    'journal': sum(p.publication_type == 'JOURNAL' for p in publications),
                    'conference': sum(p.publication_type == 'CONFERENCE' for p in publications),
                    'claimed': sum(claimed(p) for p in publications),
                    'contributed': len(publications),
                },
                'books': {
                    'books': sum(record.work_type == 'BOOK' for record in books),
                    'chapters': sum(record.work_type == 'BOOK_CHAPTER' for record in books),
                },
                'fdp': {kind: sum(record.activity_type == kind for record in fdp) for kind in ('FDP', 'STTP', 'WORKSHOP', 'WEBINAR', 'SEMINAR', 'INTERNSHIP', 'INDUSTRIAL_TRAINING')},
                'certifications': {
                    'completed': sum(item.status == 'COMPLETED' for item in certifications),
                    'in_progress': sum(item.status == 'IN_PROGRESS' for item in certifications),
                    **{kind: sum(item.category == kind for item in certifications) for kind in ('NPTEL_SWAYAM', 'MOOC', 'OTHER')},
                },
            },
            'summary': {'journal': sum(p.publication_type == 'JOURNAL' for p in publications), 'conference': sum(p.publication_type == 'CONFERENCE' for p in publications),
                        'publications_claimed': sum(claimed(p) for p in publications), 'publications_authored': len(publications), 'patents': len(event_patents), 'patents_claimed': patent_claimed, 'books': len(books), 'fdp':len(fdp),
                        # `certifications` and `funding_projects` remain for existing API consumers.
                        'certifications':len(certifications), 'certifications_completed': sum(item.status == 'COMPLETED' for item in certifications), 'certifications_in_progress': sum(item.status == 'IN_PROGRESS' for item in certifications),
                        'funding_projects': len(funding_projects), 'sponsored_research': len(funding_by_category['SPONSORED_RESEARCH']),
                        'proposals': len(funding_by_category['SPONSORED_RESEARCH']), 'consultancy': len(funding_by_category['CONSULTANCY']),
                        'internal_grants': len(funding_by_category['INTERNAL_GRANT']), **{key: None for key in UNAVAILABLE}},
            'publications': [{'id': p.id, 'title': p.title, 'publication_type': p.publication_type, 'publication_date': p.publication_date, 'claimed': claimed(p), 'indexing': p.indexing, 'quartile': p.quartile, 'classification': p.classification} for p in publications],
            'patents': [{'id': p.id, 'title': p.title, 'patent_type': p.patent_type, 'application_number': p.application_number, 'filing_date': p.filing_date, 'publication_date': p.publication_date, 'grant_date': p.grant_date, 'claimed': any(i.faculty_id == identity and i.is_claiming_faculty for i in p.inventors), 'roles': [i.person_type for i in p.inventors if i.faculty_id == identity]} for p in event_patents],
            'books': [{'id': b.id, 'title': b.title, 'work_type': b.work_type, 'publication_date': b.publication_date, 'claimed': any(c.faculty_id == identity and c.is_claiming_faculty for c in b.contributors), 'roles': [c.role for c in b.contributors if c.faculty_id == identity]} for b in books],
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
