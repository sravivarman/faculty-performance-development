"""Institutional reporting scopes built on the Phase 2 attribution service.

This service is deliberately read-only.  A parent research record is evaluated
once, then credited to every *verified* participating Department.  Therefore
Department totals are useful contribution counts but are never summed to form
the institution total.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from itertools import combinations
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .department_attribution import AttributionMode, resolve_faculty_departments
from .models import (
    BookContributor, BookPublication, Certification, Department, Faculty,
    FdpActivity, FdpParticipant, FundingProject, FundingProjectFaculty,
    Patent, PatentInventor, Publication, PublicationAuthor, Student,
)

Scope = Literal["INSTITUTION", "DEPARTMENT", "FACULTY"]
MODULES = ("publications", "patents", "books", "fdp", "certifications", "research_projects", "consultancy", "internal_grants")


def _event_in_range(value: date | None, start: date, end: date) -> bool:
    return value is not None and start <= value <= end


def _funding_date(record: FundingProject) -> date | None:
    return record.sanction_date or record.proposal_submission_date or record.start_date


def _record(module: str, identity: int, title: str, activity_date: date | None, faculty_ids: set[int], student_ids: set[int]):
    return {"module": module, "id": identity, "title": title, "activity_date": activity_date,
            "faculty_ids": faculty_ids, "student_ids": student_ids}


def _raw_records(db: Session, start: date, end: date):
    """Return one entry per parent record; joins never determine parent counts."""
    rows = []
    for item in db.scalars(select(Publication).where(Publication.is_active.is_(True), Publication.publication_date.between(start, end))):
        rows.append(_record("publications", item.id, item.title, item.publication_date,
                            {a.faculty_id for a in item.authors if a.faculty_id}, {a.student_id for a in item.authors if a.student_id}))
    for item in db.scalars(select(Patent).where(Patent.is_active.is_(True))):
        dates = [getattr(item, key) for key in ("filing_date", "publication_date", "grant_date") if _event_in_range(getattr(item, key), start, end)]
        if dates:
            rows.append(_record("patents", item.id, item.title, min(dates),
                                {i.faculty_id for i in item.inventors if i.faculty_id}, {i.student_id for i in item.inventors if i.student_id}))
    for item in db.scalars(select(BookPublication).where(BookPublication.is_active.is_(True), BookPublication.publication_date.between(start, end))):
        rows.append(_record("books", item.id, item.title, item.publication_date,
                            {c.faculty_id for c in item.contributors if c.faculty_id}, {c.student_id for c in item.contributors if c.student_id}))
    for item in db.scalars(select(FdpActivity).where(FdpActivity.is_active.is_(True), FdpActivity.start_date.between(start, end))):
        rows.append(_record("fdp", item.id, item.title, item.start_date, {p.faculty_id for p in item.participants if p.faculty_id}, set()))
    for item in db.scalars(select(Certification).where(Certification.is_active.is_(True), or_(
        Certification.completion_date.between(start, end), Certification.status == "IN_PROGRESS"))):
        # In-progress certifications are intentionally current work.  They have
        # no invented completion date, so historical attribution remains unknown.
        rows.append(_record("certifications", item.id, item.name, item.completion_date if item.status == "COMPLETED" else None,
                            {item.faculty_id}, set()))
    for item in db.scalars(select(FundingProject).where(FundingProject.is_active.is_(True))):
        when = _funding_date(item)
        if _event_in_range(when, start, end):
            module = {"SPONSORED_RESEARCH": "research_projects", "CONSULTANCY": "consultancy", "INTERNAL_GRANT": "internal_grants"}[item.category]
            rows.append(_record(module, item.id, item.title, when, {p.faculty_id for p in item.faculty if p.faculty_id}, set()))
    return rows


def _validate_scope(db: Session, scope: Scope, department_id: int | None, faculty_id: int | None):
    if scope == "DEPARTMENT":
        if department_id is None:
            raise HTTPException(422, "Department scope requires department_id")
        if db.get(Department, department_id) is None:
            raise HTTPException(422, "Unknown Department ID")
    elif department_id is not None:
        raise HTTPException(422, "department_id is valid only for Department scope")
    if scope == "FACULTY":
        if faculty_id is None:
            raise HTTPException(422, "Faculty scope requires faculty_id")
        if db.get(Faculty, faculty_id) is None:
            raise HTTPException(422, "Unknown Faculty ID")
    elif faculty_id is not None:
        raise HTTPException(422, "faculty_id is valid only for Faculty scope")


def scoped_overview(
    db: Session, *, start: date, end: date, scope: Scope = "INSTITUTION",
    department_id: int | None = None, faculty_id: int | None = None,
    attribution_mode: AttributionMode = "CURRENT",
):
    _validate_scope(db, scope, department_id, faculty_id)
    raw = _raw_records(db, start, end)
    faculty_ids = {identity for row in raw for identity in row["faculty_ids"]}
    # Preload Faculty and select-in affiliations before resolving, avoiding a
    # per-contributor lookup when a dashboard has many linked records.
    if faculty_ids:
        db.scalars(select(Faculty).where(Faculty.id.in_(faculty_ids))).all()
    student_ids = {identity for row in raw for identity in row["student_ids"]}
    students = {item.id: item for item in db.scalars(select(Student).where(Student.id.in_(student_ids))).all()} if student_ids else {}

    statuses = defaultdict(int)
    for row in raw:
        departments: set[int] = set()
        row["attributions"] = []
        for identity in row["faculty_ids"]:
            attribution = resolve_faculty_departments(db, identity, activity_date=row["activity_date"], mode=attribution_mode)
            row["attributions"].append(attribution)
            statuses[attribution["resolution_status"]] += 1
            departments.update(attribution["department_ids"])
        for identity in row["student_ids"]:
            student = students.get(identity)
            if attribution_mode == "CURRENT" and student and student.department_id is not None:
                departments.add(student.department_id)
            elif attribution_mode == "AT_ACTIVITY_DATE":
                statuses["STUDENT_HISTORICAL_AFFILIATION_UNVERIFIED"] += 1
        row["department_ids"] = departments

    def included(row):
        if scope == "INSTITUTION":
            return True
        if scope == "DEPARTMENT":
            return department_id in row["department_ids"]
        return faculty_id in row["faculty_ids"]

    selected = [row for row in raw if included(row)]
    totals = {module: sum(row["module"] == module for row in selected) for module in MODULES}
    totals["books_chapters"] = totals["books"]
    totals["unique_records"] = len(selected)
    def scoped_faculty_ids(row):
        if scope == "DEPARTMENT":
            return {item["faculty_id"] for item in row["attributions"] if department_id in item["department_ids"]}
        if scope == "FACULTY":
            return {faculty_id} if faculty_id in row["faculty_ids"] else set()
        return set(row["faculty_ids"])
    contributors = {identity for row in selected for identity in scoped_faculty_ids(row)}

    departments = db.scalars(select(Department).order_by(Department.code)).all()
    comparisons = []
    for department in departments:
        related = [row for row in raw if department.id in row["department_ids"]]
        comparisons.append({"id": department.id, "code": department.code, "name": department.name, "is_active": department.is_active,
                            "totals": {module: sum(row["module"] == module for row in related) for module in MODULES},
                            "unique_records": len(related),
                            "faculty_contributors": len({item["faculty_id"] for row in related for item in row["attributions"] if department.id in item["department_ids"]})})

    pairs = defaultdict(lambda: {"publications": 0, "patents": 0, "books": 0, "research_projects": 0, "consultancy": 0, "internal_grants": 0, "records": 0})
    collaboration_ids = set()
    for row in raw:
        if len(row["department_ids"]) < 2:
            continue
        collaboration_ids.add((row["module"], row["id"]))
        for left, right in combinations(sorted(row["department_ids"]), 2):
            pair = pairs[(left, right)]
            pair["records"] += 1
            if row["module"] in pair:
                pair[row["module"]] += 1
    department_by_id = {department.id: department for department in departments}
    collaboration = [{"department_a": {"id": left, "code": department_by_id[left].code, "name": department_by_id[left].name},
                      "department_b": {"id": right, "code": department_by_id[right].code, "name": department_by_id[right].name}, **counts}
                     for (left, right), counts in sorted(pairs.items())]
    quality = {
        "historical_affiliation_unverified": statuses["HISTORICAL_AFFILIATION_UNVERIFIED"],
        "activity_date_unknown": statuses["ACTIVITY_DATE_UNKNOWN"],
        "student_historical_affiliation_unverified": statuses["STUDENT_HISTORICAL_AFFILIATION_UNVERIFIED"],
        "no_affiliation": statuses["NO_AFFILIATION"] + statuses["NO_AFFILIATION_AT_ACTIVITY_DATE"],
        "records_without_verified_department": sum(not row["department_ids"] for row in raw),
    }
    label = "Institution" if scope == "INSTITUTION" else next((department.name for department in departments if department.id == department_id), "Department") if scope == "DEPARTMENT" else db.get(Faculty, faculty_id).name
    return {"scope": {"type": scope, "department_id": department_id, "faculty_id": faculty_id, "label": label,
                      "attribution_mode": attribution_mode, "attribution_label": "Current Department Attribution" if attribution_mode == "CURRENT" else "Activity-Date Attribution"},
            "from_date": start, "to_date": end, "totals": totals, "faculty_contributors": len(contributors),
            "records": selected, "department_comparison": comparisons,
            "collaboration": {"unique_records": len(collaboration_ids), "pairs": collaboration}, "data_quality": quality}
