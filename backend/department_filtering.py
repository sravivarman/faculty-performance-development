"""Composable Department-attribution predicates for research parent records.

This module is intentionally narrower than :mod:`scoped_reporting`: it does
not calculate dashboards or materialise records.  It produces a ``SELECT`` of
distinct parent IDs that existing list, KPI, chart and export queries can
compose with *before* counting or pagination.

The predicates implement the same Faculty affiliation semantics as
``resolve_faculty_departments``.  In particular, an activity-date request
requires a verified dated primary affiliation; a Phase 1 migration baseline
with an unknown start date is deliberately not treated as historical proof.
"""
from __future__ import annotations

from typing import Literal

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from .department_attribution import AttributionMode
from .models import (
    BookContributor,
    BookPublication,
    Certification,
    Department,
    FacultyDepartmentAffiliation,
    FdpActivity,
    FdpParticipant,
    FundingProject,
    FundingProjectFaculty,
    Patent,
    PatentInventor,
    Publication,
    PublicationAuthor,
    Student,
)

DepartmentModule = Literal[
    "publications", "patents", "books", "fdp", "certifications", "funding"
]


def _faculty_department_exists(faculty_id, department_id: int, activity_date, mode: AttributionMode, *, parent=None, contributor=None):
    """Return a correlated EXISTS for one verified primary Faculty affiliation."""
    affiliation = FacultyDepartmentAffiliation
    conditions = [
        affiliation.faculty_id == faculty_id,
        affiliation.department_id == department_id,
        affiliation.is_primary.is_(True),
    ]
    if mode == "CURRENT":
        conditions.append(affiliation.effective_to.is_(None))
    else:
        # A null activity date and a null ``effective_from`` both intentionally
        # fail this predicate.  This preserves ACTIVITY_DATE_UNKNOWN and
        # HISTORICAL_AFFILIATION_UNVERIFIED as non-attributed records.
        conditions.extend([
            activity_date.is_not(None),
            affiliation.effective_from.is_not(None),
            affiliation.effective_from <= activity_date,
            or_(affiliation.effective_to.is_(None), affiliation.effective_to >= activity_date),
        ])
    statement = select(1).where(and_(*conditions))
    # ``activity_date`` belongs to the parent record.  Explicit correlation is
    # essential for activity-date requests: without it SQLAlchemy may add a
    # second uncorrelated parent table to this nested EXISTS, allowing a dated
    # association from one record to qualify another record with no date.
    if parent is not None or contributor is not None:
        statement = statement.correlate(*[item for item in (parent, contributor) if item is not None])
    return exists(statement)


def _student_department_exists(student_id, department_id: int, mode: AttributionMode):
    """Student attribution is available only for the current Department view."""
    if student_id is None or mode != "CURRENT":
        return False
    return exists(select(1).where(Student.id == student_id, Student.department_id == department_id))


def _parent_ids(parent, contributor, parent_key, faculty_key, student_key, activity_date, department_id: int, mode: AttributionMode):
    faculty_match = exists(select(1).where(
        parent_key == parent.id,
        faculty_key.is_not(None),
        _faculty_department_exists(faculty_key, department_id, activity_date, mode, parent=parent, contributor=contributor),
    ))
    student_match = _student_department_exists(student_key, department_id, mode)
    if student_match is False:
        return select(parent.id).where(faculty_match)
    student_match = exists(select(1).where(
        parent_key == parent.id,
        student_key.is_not(None),
        student_match,
    ))
    return select(parent.id).where(or_(faculty_match, student_match))


def eligible_department_record_ids(
    db: Session,
    module: DepartmentModule,
    department_id: int,
    *,
    attribution_mode: AttributionMode = "CURRENT",
    activity_date=None,
):
    """Select distinct parent IDs attributed to ``department_id``.

    ``activity_date`` optionally overrides the module's normal reporting-date
    column.  Patent lifecycle callers should pass the selected lifecycle event
    date when their report is event-specific; the default is the filing date.
    The returned select is designed for ``Parent.id.in_(...)`` composition.
    """
    if attribution_mode not in ("CURRENT", "AT_ACTIVITY_DATE"):
        raise ValueError("attribution_mode must be CURRENT or AT_ACTIVITY_DATE")
    if db.get(Department, department_id) is None:
        raise ValueError("Unknown Department ID")

    if module == "publications":
        return _parent_ids(Publication, PublicationAuthor, PublicationAuthor.publication_id,
                           PublicationAuthor.faculty_id, PublicationAuthor.student_id,
                           activity_date if activity_date is not None else Publication.publication_date,
                           department_id, attribution_mode)
    if module == "patents":
        return _parent_ids(Patent, PatentInventor, PatentInventor.patent_id,
                           PatentInventor.faculty_id, PatentInventor.student_id,
                           activity_date if activity_date is not None else Patent.filing_date,
                           department_id, attribution_mode)
    if module == "books":
        return _parent_ids(BookPublication, BookContributor, BookContributor.book_record_id,
                           BookContributor.faculty_id, BookContributor.student_id,
                           activity_date if activity_date is not None else BookPublication.publication_date,
                           department_id, attribution_mode)
    if module == "fdp":
        return _parent_ids(FdpActivity, FdpParticipant, FdpParticipant.activity_id,
                           FdpParticipant.faculty_id, None,
                           activity_date if activity_date is not None else FdpActivity.start_date,
                           department_id, attribution_mode)
    if module == "certifications":
        faculty_match = _faculty_department_exists(
            Certification.faculty_id,
            department_id,
            activity_date if activity_date is not None else Certification.completion_date,
            attribution_mode,
            parent=Certification,
        )
        return select(Certification.id).where(faculty_match)
    if module == "funding":
        return _parent_ids(FundingProject, FundingProjectFaculty, FundingProjectFaculty.funding_project_id,
                           FundingProjectFaculty.faculty_id, None,
                           activity_date if activity_date is not None else FundingProject.sanction_date,
                           department_id, attribution_mode)
    raise ValueError(f"Unsupported Department filtering module: {module}")


def department_record_predicate(db: Session, module: DepartmentModule, department_id: int, *, attribution_mode: AttributionMode = "CURRENT", activity_date=None):
    """Return a parent-ID predicate suitable for an existing SQLAlchemy query."""
    parent = {
        "publications": Publication,
        "patents": Patent,
        "books": BookPublication,
        "fdp": FdpActivity,
        "certifications": Certification,
        "funding": FundingProject,
    }[module]
    return parent.id.in_(eligible_department_record_ids(
        db, module, department_id, attribution_mode=attribution_mode, activity_date=activity_date
    ))
