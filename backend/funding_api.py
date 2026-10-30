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
FundingRole = Literal["LEAD_PI", "MEMBER_PI", "CO_PI", "ADMIN_PI", "BENEFICIARY", "PI", "CO_INVESTIGATOR"]
CATEGORIES = ("SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT")
STATUSES = ("DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN")
ROLES = ("LEAD_PI", "MEMBER_PI", "CO_PI", "ADMIN_PI", "BENEFICIARY")
LEGACY_ROLES = {"PI", "CO_INVESTIGATOR"}
PI_LEVEL_ROLES = {"LEAD_PI", "MEMBER_PI", "PI"}
SANCTIONED_STATUSES = {"SANCTIONED", "ONGOING", "COMPLETED"}
FINANCIAL_METRICS = {"sanctioned_amount", "contract_value", "amount_received", "amount_utilized"}
FINANCIAL_METRIC_FIELDS = {
    "sanctioned_amount": "sanctioned_amount",
    "contract_value": "contract_amount",
    "amount_received": "amount_received",
    "amount_utilized": "amount_utilized",
}


class FundingFacultyInput(BaseModel):
    id: int | None = None
    faculty_id: int | None = None
    role: FundingRole
    investigator_name: str | None = Field(default=None, max_length=500)
    department_name: str | None = Field(default=None, max_length=250)
    institution_name: str | None = Field(default=None, max_length=500)
    agency_role_label: str | None = Field(default=None, max_length=100)
    is_designated_lead: bool = False

    @model_validator(mode="after")
    def validate_identity(self):
        manual_name = (self.investigator_name or "").strip()
        if self.faculty_id is None and not manual_name:
            raise ValueError("Select a Faculty Master investigator or enter an investigator name")
        if self.faculty_id is not None and manual_name:
            raise ValueError("A linked Faculty investigator cannot also retain manual investigator details")
        if self.role == "LEAD_PI":
            self.is_designated_lead = True
        return self


class FundingProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    category: FundingCategory
    department: str = Field(min_length=1, max_length=250)
    funding_agency: str | None = Field(default=None, max_length=2000)
    proposal_submission_date: date | None = None
    sanction_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    proposed_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    sanctioned_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    contract_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
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
        identities = [
            ("FACULTY", member.faculty_id, member.role) if member.faculty_id is not None
            else ("MANUAL", member.investigator_name, member.department_name, member.institution_name, member.role)
            for member in self.faculty
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("A Faculty member may be assigned each project role only once")
        if self.category in {"SPONSORED_RESEARCH", "CONSULTANCY"} and not any(member.role in PI_LEVEL_ROLES for member in self.faculty):
            raise ValueError("Sponsored research and consultancy records require at least one PI-level investigator")
        if sum(member.is_designated_lead for member in self.faculty) > 1:
            raise ValueError("Only one designated overall lead is allowed for a project")
        if self.status in SANCTIONED_STATUSES and not self.sanction_date:
            raise ValueError("Sanction date is required for sanctioned, ongoing, or completed records")
        return self


def faculty_or_422(db: Session, identity: int) -> Faculty:
    faculty = db.get(Faculty, identity)
    if not faculty:
        raise HTTPException(422, "Select an existing Faculty Master record")
    return faculty


def funding_dict(record: FundingProject, db: Session):
    faculty = []
    for member in sorted(record.faculty, key=lambda member: (member.display_order, member.id)):
        value = columns(member)
        if member.faculty_id is not None:
            person = faculty_or_422(db, member.faculty_id)
            value.update({"faculty_name": person.name, "employee_id": person.employee_id,
                          "is_active": person.is_active, "affiliation_type": "FACULTY_MASTER"})
        else:
            value.update({"faculty_name": member.investigator_name, "employee_id": None,
                          "is_active": None, "affiliation_type": "MANUAL"})
        faculty.append(value)
    values = columns(record)
    values["faculty"] = faculty
    values["evidence_count"] = len(record.evidence)
    values["proposed_amount_lakhs"] = record.proposed_amount / Decimal("100000") if record.proposed_amount is not None else None
    values["sanctioned_amount_lakhs"] = record.sanctioned_amount / Decimal("100000") if record.sanctioned_amount is not None else None
    values["contract_amount_lakhs"] = record.contract_amount / Decimal("100000") if record.contract_amount is not None else None
    values["amount_received_lakhs"] = record.amount_received / Decimal("100000") if record.amount_received is not None else None
    values["amount_utilized_lakhs"] = record.amount_utilized / Decimal("100000") if record.amount_utilized is not None else None
    values["reporting_date"] = record.sanction_date or record.proposal_submission_date or record.start_date
    return values


def save_project(db: Session, data: FundingProjectInput, record: FundingProject | None = None):
    is_new = record is None
    record = record or FundingProject()
    existing_members = {member.id: member for member in record.faculty} if not is_new else {}
    for member in data.faculty:
        if member.role in LEGACY_ROLES:
            historical = existing_members.get(member.id)
            if not historical or historical.role != member.role:
                raise HTTPException(422, "Historical PI and Co-Investigator roles are preserved for existing records only. Select one of the five active roles for a new investigator.")
        if member.faculty_id is not None:
            faculty_or_422(db, member.faculty_id)
        if member.role != "LEAD_PI" and member.is_designated_lead:
            historical = existing_members.get(member.id)
            if not historical or not historical.is_designated_lead:
                raise HTTPException(422, "Only LEAD_PI automatically designates the overall lead")
    for key, value in data.model_dump(exclude={"faculty"}).items():
        setattr(record, key, value)
    if not is_new:
        record.faculty.clear()
        db.flush()
    record.faculty.extend(FundingProjectFaculty(
        faculty_id=member.faculty_id,
        role=member.role,
        investigator_name=(member.investigator_name or "").strip() or None,
        department_name=(member.department_name or "").strip() or None,
        institution_name=(member.institution_name or "").strip() or None,
        affiliation_type="FACULTY_MASTER" if member.faculty_id is not None else "MANUAL",
        agency_role_label=(member.agency_role_label or "").strip() or None,
        is_designated_lead=member.is_designated_lead,
        display_order=index,
    ) for index, member in enumerate(data.faculty, start=1))
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
    if metric in FINANCIAL_METRICS:
        field = FINANCIAL_METRIC_FIELDS[metric]
        return [record for record in records if record.status in SANCTIONED_STATUSES and getattr(record, field) is not None]
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


def funding_dashboard_data(db: Session, selected: dict, from_date: date, to_date: date):
    """Return the shared, unpaginated funding summary for one reporting scope.

    The overview dashboard uses this service directly so it cannot accidentally
    calculate amounts from a paginated list or from investigator associations.
    """
    records = filtered_projects(db, selected, from_date, to_date)
    faculty_counts: dict[int, int] = {}
    faculty_role_counts: dict[int, dict[str, int]] = {}
    faculty_departments: dict[int, set[str]] = {}
    faculty_roles: dict[int, list[str]] = {}
    for record in records:
        for identity in {member.faculty_id for member in record.faculty if member.faculty_id is not None}:
            faculty_counts[identity] = faculty_counts.get(identity, 0) + 1
            faculty_departments.setdefault(identity, set()).add(record.department)
        for member in record.faculty:
            if member.faculty_id is not None:
                counts = faculty_role_counts.setdefault(member.faculty_id, {role: 0 for role in ROLES})
                reporting_role = "CO_PI" if member.role == "CO_INVESTIGATOR" else member.role
                if reporting_role in counts:
                    counts[reporting_role] += 1
                display_role = member.agency_role_label or member.role
                roles = faculty_roles.setdefault(member.faculty_id, [])
                if display_role not in roles:
                    roles.append(display_role)
    people = {person.id: person for person in db.scalars(select(Faculty).where(Faculty.id.in_(faculty_counts)))}
    faculty = [
        {"id": identity, "name": people[identity].name, "employee_id": people[identity].employee_id,
         "is_active": people[identity].is_active, "projects": count,
         "department": ", ".join(sorted(faculty_departments.get(identity, set()))),
         "roles": faculty_roles.get(identity, []),
         **{f"role_{role.lower()}": faculty_role_counts.get(identity, {}).get(role, 0) for role in ROLES}}
        for identity, count in sorted(faculty_counts.items(), key=lambda item: people[item[0]].name.lower())
    ]
    submitted = sum(record.status in {"SUBMITTED", "UNDER_REVIEW"} for record in records)
    sanctioned = sum(record.status in SANCTIONED_STATUSES for record in records)
    awarded_records = [record for record in records if record.status in SANCTIONED_STATUSES]
    totals = {
        "total": len(records), "submitted_under_review": submitted, "sanctioned": sanctioned,
        "ongoing": sum(record.status == "ONGOING" for record in records),
        "completed": sum(record.status == "COMPLETED" for record in records),
        "proposed_amount": amount(records, "proposed_amount"),
        "sanctioned_amount": amount(awarded_records, "sanctioned_amount"),
        "contract_value": amount(awarded_records, "contract_amount"),
        "amount_received": amount(awarded_records, "amount_received"),
        "amount_utilized": amount(awarded_records, "amount_utilized"),
        "faculty_beneficiaries": len(faculty_counts),
        "faculty_contributors": len(faculty_counts),
    }
    return {"totals": totals, "faculty": faculty,
            "role_counts": {role: sum(member.role == role for record in records for member in record.faculty) for role in ROLES}}


@router.get("/funding-dashboard")
def funding_dashboard(
    db: DB,
    selected: Annotated[dict, Depends(project_filters)],
    from_date: date,
    to_date: date,
):
    return funding_dashboard_data(db, selected, from_date, to_date)
