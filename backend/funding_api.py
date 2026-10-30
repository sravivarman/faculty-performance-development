"""CRUD, reporting and lifecycle endpoints for department funding records."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Faculty, FundingProject, FundingProjectChangeLog, FundingProjectFaculty
from .pagination import PageSize, paginate_records
from .reporting import validate_date_range
from .services import columns


router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
FundingCategory = Literal["SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT"]
FundingStatus = Literal["DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN"]
FundingRole = Literal["PI", "CO_PI", "BENEFICIARY"]
CATEGORIES = ("SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT")
STATUSES = ("DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN")
ROLES = ("PI", "CO_PI", "BENEFICIARY")
SANCTIONED_STATUSES = {"SANCTIONED", "ONGOING", "COMPLETED"}


class FundingFacultyInput(BaseModel):
    faculty_id: int
    role: FundingRole


class FundingProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    category: FundingCategory
    department: str = Field(min_length=1, max_length=250)
    funding_agency: str | None = Field(default=None, max_length=2000)
    proposal_submission_date: date | None = None
    sanction_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    sanctioned_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    amount_received: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    amount_utilized: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    reference_number: str | None = Field(default=None, max_length=250)
    status: FundingStatus = "DRAFT"
    description: str | None = None
    outcomes: str | None = None
    deliverables: str | None = None
    completion_details: str | None = None
    internal_notes: str | None = None
    source_url: str | None = None
    faculty: list[FundingFacultyInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_project(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("Project end date must be on or after the start date")
        pairs = [(member.faculty_id, member.role) for member in self.faculty]
        if len(pairs) != len(set(pairs)):
            raise ValueError("A Faculty member may be assigned each project role only once")
        if sum(member.role == "PI" for member in self.faculty) != 1:
            raise ValueError("Select exactly one Principal Investigator")
        if self.status in SANCTIONED_STATUSES and not self.sanction_date:
            raise ValueError("Sanction date is required for sanctioned, ongoing, or completed records")
        return self


def faculty_or_422(db: Session, identity: int) -> Faculty:
    faculty = db.get(Faculty, identity)
    if not faculty:
        raise HTTPException(422, "Select an existing Faculty Master record")
    return faculty


def funding_dict(record: FundingProject, db: Session):
    faculty = [
        {**columns(member), "faculty_name": faculty_or_422(db, member.faculty_id).name,
         "employee_id": faculty_or_422(db, member.faculty_id).employee_id,
         "is_active": faculty_or_422(db, member.faculty_id).is_active}
        for member in sorted(record.faculty, key=lambda member: (ROLES.index(member.role), member.faculty_id))
    ]
    values = columns(record)
    values["faculty"] = faculty
    values["evidence_count"] = len(record.evidence)
    values["sanctioned_amount_lakhs"] = record.sanctioned_amount / Decimal("100000") if record.sanctioned_amount is not None else None
    values["amount_received_lakhs"] = record.amount_received / Decimal("100000") if record.amount_received is not None else None
    values["amount_utilized_lakhs"] = record.amount_utilized / Decimal("100000") if record.amount_utilized is not None else None
    values["reporting_date"] = record.sanction_date or record.proposal_submission_date or record.start_date
    return values


def save_project(db: Session, data: FundingProjectInput, record: FundingProject | None = None):
    is_new = record is None
    record = record or FundingProject()
    for member in data.faculty:
        faculty_or_422(db, member.faculty_id)
    for key, value in data.model_dump(exclude={"faculty"}).items():
        setattr(record, key, value)
    if not is_new:
        record.faculty.clear()
        db.flush()
    record.faculty.extend(FundingProjectFaculty(faculty_id=member.faculty_id, role=member.role) for member in data.faculty)
    db.add(record)
    db.flush()
    db.add(FundingProjectChangeLog(
        funding_project_id=record.id,
        action="CREATE" if is_new else "UPDATE",
        changes={"title": record.title, "status": record.status},
    ))
    db.commit()
    db.refresh(record)
    return record


def get_project(db: Session, identity: int) -> FundingProject:
    record = db.get(FundingProject, identity)
    if not record:
        raise HTTPException(404, "Funding record not found")
    return record


def project_filters(
    category: FundingCategory | None = None,
    faculty_id: int | None = None,
    department: str | None = None,
    funding_agency: str | None = None,
    status: FundingStatus | None = None,
    search: str | None = None,
    include_inactive: bool = False,
):
    return locals()


def filtered_projects(db: Session, filters: dict, from_date: date | None = None, to_date: date | None = None):
    validate_date_range(from_date, to_date, required=False)
    query = select(FundingProject)
    if not filters["include_inactive"]:
        query = query.where(FundingProject.is_active.is_(True))
    for key in ("category", "status"):
        if filters[key]:
            query = query.where(getattr(FundingProject, key) == filters[key])
    if filters["faculty_id"]:
        query = query.where(FundingProject.faculty.any(FundingProjectFaculty.faculty_id == filters["faculty_id"]))
    if filters["department"]:
        query = query.where(FundingProject.department.ilike(f"%{filters['department']}%"))
    if filters["funding_agency"]:
        query = query.where(FundingProject.funding_agency.ilike(f"%{filters['funding_agency']}%"))
    if filters["search"]:
        search = f"%{filters['search']}%"
        query = query.where(or_(
            FundingProject.title.ilike(search),
            FundingProject.funding_agency.ilike(search),
            FundingProject.department.ilike(search),
            FundingProject.faculty.any(FundingProjectFaculty.faculty_id.in_(select(Faculty.id).where(Faculty.name.ilike(search)))),
        ))
    reporting_date = func.coalesce(FundingProject.sanction_date, FundingProject.proposal_submission_date, FundingProject.start_date)
    if from_date:
        query = query.where(reporting_date.between(from_date, to_date))
    return db.scalars(query.order_by(reporting_date.desc(), FundingProject.id.desc())).unique().all()


def metric_records(records: list[FundingProject], metric: str | None):
    if not metric or metric == "total":
        return records
    if metric == "submitted_under_review":
        return [record for record in records if record.status in {"SUBMITTED", "UNDER_REVIEW"}]
    if metric == "sanctioned":
        return [record for record in records if record.status in SANCTIONED_STATUSES]
    if metric in {"ongoing", "completed"}:
        return [record for record in records if record.status == metric.upper()]
    if metric in {"sanctioned_amount", "contract_value", "amount_received", "amount_utilized"}:
        return records
    raise HTTPException(422, "Unknown funding dashboard metric")


@router.get("/funding-project-options")
def funding_options(db: DB):
    departments = list(db.scalars(select(FundingProject.department).distinct().order_by(FundingProject.department)))
    agencies = list(db.scalars(select(FundingProject.funding_agency).where(FundingProject.funding_agency.is_not(None)).distinct().order_by(FundingProject.funding_agency)))
    return {"categories": CATEGORIES, "statuses": STATUSES, "faculty_roles": ROLES, "departments": departments, "funding_agencies": agencies}


@router.post("/funding-projects", status_code=201)
def create_project(data: FundingProjectInput, db: DB):
    return funding_dict(save_project(db, data), db)


@router.get("/funding-projects")
def list_projects(
    db: DB,
    selected: Annotated[dict, Depends(project_filters)],
    from_date: date | None = None,
    to_date: date | None = None,
    metric: str | None = None,
    page: int | None = None,
    page_size: PageSize = 25,
):
    records = metric_records(filtered_projects(db, selected, from_date, to_date), metric)
    return paginate_records(records, page, page_size, lambda record: funding_dict(record, db))


@router.get("/funding-projects/{identity}")
def project_detail(identity: int, db: DB):
    record = get_project(db, identity)
    return {**funding_dict(record, db), "change_log": [columns(row) for row in db.scalars(
        select(FundingProjectChangeLog).where(FundingProjectChangeLog.funding_project_id == identity).order_by(FundingProjectChangeLog.id.desc())
    )]}


@router.put("/funding-projects/{identity}")
def update_project(identity: int, data: FundingProjectInput, db: DB):
    return funding_dict(save_project(db, data, get_project(db, identity)), db)


@router.delete("/funding-projects/{identity}")
def deactivate_project(identity: int, db: DB):
    record = get_project(db, identity)
    record.is_active = False
    db.add(FundingProjectChangeLog(funding_project_id=identity, action="DEACTIVATE", changes={"is_active": False}))
    db.commit()
    return {"id": identity, "is_active": False}


@router.post("/funding-projects/{identity}/reactivate")
def reactivate_project(identity: int, db: DB):
    record = get_project(db, identity)
    if record.is_active:
        raise HTTPException(409, "Funding record is already active")
    record.is_active = True
    db.add(FundingProjectChangeLog(funding_project_id=identity, action="REACTIVATE", changes={"is_active": True}))
    db.commit()
    return funding_dict(record, db)


def amount(records: list[FundingProject], field: str) -> Decimal:
    return sum((getattr(record, field) or Decimal("0") for record in records), Decimal("0"))


@router.get("/funding-dashboard")
def funding_dashboard(
    db: DB,
    selected: Annotated[dict, Depends(project_filters)],
    from_date: date,
    to_date: date,
):
    records = filtered_projects(db, selected, from_date, to_date)
    faculty_counts: dict[int, int] = {}
    for record in records:
        for identity in {member.faculty_id for member in record.faculty}:
            faculty_counts[identity] = faculty_counts.get(identity, 0) + 1
    people = {person.id: person for person in db.scalars(select(Faculty).where(Faculty.id.in_(faculty_counts)))}
    faculty = [
        {"id": identity, "name": people[identity].name, "employee_id": people[identity].employee_id,
         "is_active": people[identity].is_active, "projects": count}
        for identity, count in sorted(faculty_counts.items(), key=lambda item: people[item[0]].name.lower())
    ]
    submitted = sum(record.status in {"SUBMITTED", "UNDER_REVIEW"} for record in records)
    sanctioned = sum(record.status in SANCTIONED_STATUSES for record in records)
    totals = {
        "total": len(records), "submitted_under_review": submitted, "sanctioned": sanctioned,
        "ongoing": sum(record.status == "ONGOING" for record in records),
        "completed": sum(record.status == "COMPLETED" for record in records),
        "sanctioned_amount": amount(records, "sanctioned_amount"),
        "contract_value": amount(records, "sanctioned_amount"),
        "amount_received": amount(records, "amount_received"),
        "amount_utilized": amount(records, "amount_utilized"),
        "faculty_beneficiaries": len(faculty_counts),
    }
    return {"totals": totals, "faculty": faculty}
