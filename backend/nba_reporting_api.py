"""Read-only NBA funding-report preparation based on the Academic Year Master."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .funding_api import SANCTIONED_STATUSES, funding_dict
from .models import AcademicYear, FundingProject


router = APIRouter(prefix="/nba")
DB = Annotated[Session, Depends(get_db)]
FundingCategory = Literal["SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT"]
FundingStatus = Literal["DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN"]
DateBasis = Literal["SANCTION_DATE", "PROPOSAL_SUBMISSION_DATE", "START_DATE"]

TABLES = {
    "SPONSORED_RESEARCH": "NBA Table 6.2.4.1 — Sponsored Research",
    "CONSULTANCY": "NBA Table 6.2.5.1 — Consultancy Projects",
    "INTERNAL_GRANT": "NBA Table 6.2.6.1 — Seed Money / Internal Grants",
}
DATE_BASES = {
    "SANCTION_DATE": {"field": "sanction_date", "label": "Sanction / approval date"},
    "PROPOSAL_SUBMISSION_DATE": {"field": "proposal_submission_date", "label": "Proposal submission date"},
    "START_DATE": {"field": "start_date", "label": "Project start date"},
}
DEFAULT_DATE_POLICY = {
    "SPONSORED_RESEARCH": {"date_basis": "SANCTION_DATE", "label": "Sanction date"},
    "CONSULTANCY": {"date_basis": "SANCTION_DATE", "label": "Approval / award date"},
    "INTERNAL_GRANT": {"date_basis": "SANCTION_DATE", "label": "Institutional sanction date"},
}


def academic_year_or_404(db: Session, identity: int) -> AcademicYear:
    year = db.get(AcademicYear, identity)
    if not year:
        raise HTTPException(404, "Academic Year Master record not found")
    return year


def relative_years(db: Session, reference: AcademicYear, count: int):
    """Derive CAY labels from persisted master rows, never from fixed dates."""
    years = list(db.scalars(
        select(AcademicYear)
        .where(AcademicYear.start_date <= reference.start_date)
        .order_by(AcademicYear.start_date.desc(), AcademicYear.id.desc())
        .limit(count)
    ))
    return [
        {"code": "CAY" if index == 0 else f"CAYm{index}", "academic_year": year}
        for index, year in enumerate(years)
    ]


def date_basis_label(category: FundingCategory, selected_basis: DateBasis) -> str:
    """Use category policy wording for the default, generic wording for overrides."""
    default = DEFAULT_DATE_POLICY[category]
    return default["label"] if selected_basis == default["date_basis"] else DATE_BASES[selected_basis]["label"]


@router.get("/funding-reporting-options")
def funding_reporting_options(db: DB):
    """Expose existing Academic Year Master records and explicit default policy."""
    years = list(db.scalars(select(AcademicYear).order_by(AcademicYear.start_date.desc(), AcademicYear.id.desc())))
    return {
        "academic_years": [
            {"id": year.id, "name": year.name, "start_date": year.start_date, "end_date": year.end_date}
            for year in years
        ],
        "reports": [
            {
                "category": category,
                "table": table,
                "default_date_basis": DEFAULT_DATE_POLICY[category]["date_basis"],
                "default_date_basis_label": DEFAULT_DATE_POLICY[category]["label"],
            }
            for category, table in TABLES.items()
        ],
        "date_bases": [{"value": key, **value} for key, value in DATE_BASES.items()],
        "default_eligible_statuses": sorted(SANCTIONED_STATUSES),
    }


@router.get("/funding-reports/{category}")
def funding_report_preview(
    category: FundingCategory,
    reference_academic_year_id: int,
    db: DB,
    relative_year_count: int = Query(default=3, ge=1, le=10),
    date_basis: DateBasis | None = None,
    eligible_status: list[FundingStatus] | None = Query(default=None),
    include_inactive: bool = False,
):
    """Prepare, but do not export, an NBA funding report from master-year dates."""
    reference = academic_year_or_404(db, reference_academic_year_id)
    selected_basis = date_basis or DEFAULT_DATE_POLICY[category]["date_basis"]
    basis = DATE_BASES[selected_basis]
    eligible_statuses = set(eligible_status or SANCTIONED_STATUSES)
    query = select(FundingProject).where(FundingProject.category == category)
    if not include_inactive:
        query = query.where(FundingProject.is_active.is_(True))
    all_records = list(db.scalars(query.order_by(FundingProject.id.desc())).unique())
    records = [record for record in all_records if record.status in eligible_statuses]
    periods = relative_years(db, reference, relative_year_count)
    result = []
    incomplete = []
    assigned_ids = set()
    for period in periods:
        year = period["academic_year"]
        matching = []
        for record in records:
            reporting_date = getattr(record, basis["field"])
            if reporting_date is None:
                continue
            if year.start_date <= reporting_date <= year.end_date:
                matching.append(funding_dict(record, db))
                assigned_ids.add(record.id)
        result.append({
            "code": period["code"],
            "academic_year": {"id": year.id, "name": year.name, "start_date": year.start_date, "end_date": year.end_date},
            "records": matching,
            "count": len(matching),
        })
    for record in all_records:
        if getattr(record, basis["field"]) is None:
            incomplete.append({
                "id": record.id,
                "title": record.title,
                "status": record.status,
                "missing_field": basis["field"],
                "missing_label": date_basis_label(category, selected_basis),
                "eligible_for_selected_policy": record.status in eligible_statuses,
            })
    return {
        "table": TABLES[category],
        "category": category,
        "reference_academic_year": {"id": reference.id, "name": reference.name, "start_date": reference.start_date, "end_date": reference.end_date},
        "policy": {
            "date_basis": selected_basis,
            "date_field": basis["field"],
            "date_basis_label": date_basis_label(category, selected_basis),
            "eligible_statuses": sorted(eligible_statuses),
            "include_inactive": include_inactive,
            "note": "The default date basis is an application policy for review, not an NBA rule. Change it before export if the institution adopts another basis.",
        },
        "periods": result,
        "incomplete_records": incomplete,
        "outside_selected_relative_years": sum(
            getattr(record, basis["field"]) is not None and record.id not in assigned_ids
            for record in records
        ),
    }
