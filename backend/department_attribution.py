"""Reusable Department attribution for Faculty Master-linked contributors.

This module deliberately resolves attribution without changing record ownership
or dashboard calculations.  It is the Phase 2 foundation for later reporting.
"""

from datetime import date
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from .models import Faculty, FacultyDepartmentAffiliation


AttributionMode = Literal["CURRENT", "AT_ACTIVITY_DATE"]


class DepartmentAttribution(TypedDict):
    faculty_id: int
    department_ids: list[int]
    department_codes: list[str]
    attribution_mode: AttributionMode
    resolution_status: str
    date_used: date | None
    provenance: str


def resolve_faculty_departments(
    db: Session,
    faculty_id: int,
    *,
    activity_date: date | None = None,
    mode: AttributionMode = "AT_ACTIVITY_DATE",
) -> DepartmentAttribution:
    """Resolve a Faculty member's Department without inventing past dates.

    ``CURRENT`` uses the current primary affiliation.  ``AT_ACTIVITY_DATE``
    uses a dated primary interval; a Phase 1 migration-baseline interval with
    no known start date is reported as unverified instead of credited as fact.
    """
    person = db.get(Faculty, faculty_id)
    result: DepartmentAttribution = {
        "faculty_id": faculty_id,
        "department_ids": [],
        "department_codes": [],
        "attribution_mode": mode,
        "resolution_status": "FACULTY_NOT_FOUND" if person is None else "NO_AFFILIATION",
        "date_used": activity_date if mode == "AT_ACTIVITY_DATE" else None,
        "provenance": "NONE",
    }
    if person is None:
        return result

    affiliations = [item for item in person.department_affiliations if item.is_primary]
    if mode == "CURRENT":
        current = [item for item in affiliations if item.effective_to is None]
        if not current:
            return result
        affiliation = max(current, key=lambda item: (item.effective_from or date.min, item.id))
        result.update(
            department_ids=[affiliation.department_id],
            department_codes=[affiliation.department.code] if affiliation.department else [],
            resolution_status="CURRENT_AFFILIATION_RESOLVED",
            provenance=affiliation.source,
        )
        return result

    if activity_date is None:
        result.update(resolution_status="ACTIVITY_DATE_UNKNOWN", provenance="NO_ACTIVITY_DATE")
        return result
    dated = [
        item for item in affiliations
        if item.effective_from is not None
        and item.effective_from <= activity_date
        and (item.effective_to is None or item.effective_to >= activity_date)
    ]
    if dated:
        result.update(
            department_ids=[item.department_id for item in dated],
            department_codes=[item.department.code for item in dated if item.department],
            resolution_status="ACTIVITY_DATE_AFFILIATION_RESOLVED",
            provenance="DATED_AFFILIATION",
        )
        return result
    if any(item.effective_from is None and item.source == "MIGRATION_BASELINE" for item in affiliations):
        result.update(
            resolution_status="HISTORICAL_AFFILIATION_UNVERIFIED",
            provenance="MIGRATION_BASELINE_WITH_UNKNOWN_START",
        )
    else:
        result.update(resolution_status="NO_AFFILIATION_AT_ACTIVITY_DATE", provenance="DATED_AFFILIATION")
    return result
