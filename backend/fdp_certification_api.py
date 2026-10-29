"""Coordinator-facing CRUD for Faculty Development Activities and certifications."""
from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from . import db as database
from .db import get_db
from .models import Certification, CertificationChangeLog, EvidenceFile, Faculty, FdpActivity, FdpChangeLog, FdpParticipant, FdpSpeaker
from .pagination import ALLOWED_PAGE_SIZES, PageSize
from .reporting import validate_date_range
from .services import columns

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
ACTIVITY_TYPES = ("FDP","STTP","WORKSHOP","WEBINAR","SEMINAR","INTERNSHIP","INDUSTRIAL_TRAINING")
ROLES = ("ATTENDEE","RESOURCE_PERSON","ORGANIZER","CONDUCTOR","PARTICIPANT","TRAINEE","COLLABORATOR","OTHER")

def monthly_rows(start: date, end: date, records, date_key: str, labels: dict[str, callable]):
    """Inclusive month buckets built from the complete, unpaginated report set."""
    cursor = date(start.year, start.month, 1)
    rows = []
    while cursor <= end:
        next_month = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        rows.append({"month": cursor.strftime("%Y-%m"), **{
            key: sum(predicate(row) and cursor <= row[date_key] < next_month for row in records if row.get(date_key))
            for key, predicate in labels.items()
        }})
        cursor = next_month
    return rows

class ActivityParticipantInput(BaseModel):
    faculty_id: int
    role: Literal["ATTENDEE","RESOURCE_PERSON","ORGANIZER","CONDUCTOR","PARTICIPANT","TRAINEE","COLLABORATOR","OTHER"]
class SpeakerInput(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    designation: str|None=None; organization: str|None=None; location_or_contact: str|None=None
class ActivityInput(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    activity_type: Literal["FDP","STTP","WORKSHOP","WEBINAR","SEMINAR","INTERNSHIP","INDUSTRIAL_TRAINING"]
    organizing_institution: str = Field(min_length=1, max_length=2000)
    start_date: date; end_date: date|None=None
    duration_value: float = Field(gt=0); duration_unit: Literal["HOURS","DAYS","WEEKS","MONTHS"]
    location: str|None=None; mode: Literal["PHYSICAL","ONLINE","HYBRID"]|None=None; description: str|None=None; source_url: str|None=None; outcomes: str|None=None; internal_notes: str|None=None
    attendance_count: int|None = Field(default=None, ge=0); company_location: str|None=None
    participants: list[ActivityParticipantInput] = Field(min_length=1); speakers: list[SpeakerInput] = Field(default_factory=list)
    @model_validator(mode="after")
    def validate_activity(self):
        if self.end_date and self.end_date < self.start_date: raise ValueError("End date must be on or after start date")
        identities=[(p.faculty_id,p.role) for p in self.participants]
        if len(identities)!=len(set(identities)): raise ValueError("A Faculty participant and role may be added only once")
        return self
class CertificationInput(BaseModel):
    faculty_id: int; name: str=Field(min_length=1,max_length=2000); category: Literal["NPTEL_SWAYAM","MOOC","OTHER"]
    provider: str=Field(min_length=1,max_length=2000); course_url: str|None=None; credential_id: str|None=None
    issue_date: date|None=None; completion_date: date|None=None; expiry_date: date|None=None; grade_score: str|None=None; grade_scale: str|None=None
    status: Literal["COMPLETED","IN_PROGRESS"]; notes: str|None=None
    @model_validator(mode="after")
    def validate_dates(self):
        if self.status == "COMPLETED" and not self.completion_date: raise ValueError("Completion date is required for completed certifications")
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date: raise ValueError("Expiry date cannot precede issue date")
        if self.issue_date and self.completion_date and self.completion_date > self.issue_date: raise ValueError("Completion date cannot be after issue date")
        return self

def faculty_or_422(db, identity):
    person=db.get(Faculty,identity)
    if not person: raise HTTPException(422,"Select an existing Faculty Master record")
    return person
def activity_dict(row, db):
    value=columns(row); value["participants"]= [{**columns(p),"faculty_name":faculty_or_422(db,p.faculty_id).name} for p in row.participants]
    value["speakers"]=[columns(s) for s in row.speakers]; value["evidence_count"]=len(row.evidence); return value
def certification_dict(row, db):
    return {**columns(row),"faculty_name":faculty_or_422(db,row.faculty_id).name,"evidence_count":len(row.evidence)}
def save_activity(db, data, row=None):
    is_new = row is None; row=row or FdpActivity()
    for key,value in data.model_dump(exclude={"participants","speakers"}).items(): setattr(row,key,value)
    for p in data.participants: faculty_or_422(db,p.faculty_id)
    if not is_new:
        # Flush orphan removal before adding replacement rows. SQLite otherwise
        # sees an INSERT for an unchanged (activity, Faculty, role) pair before
        # the old row's DELETE and correctly raises its unique constraint.
        row.participants.clear()
        row.speakers.clear()
        db.flush()
    row.participants.extend(FdpParticipant(faculty_id=p.faculty_id,role=p.role) for p in data.participants)
    row.speakers.extend(FdpSpeaker(**s.model_dump()) for s in data.speakers)
    db.add(row); db.flush(); db.add(FdpChangeLog(activity_id=row.id,action="CREATE" if is_new else "UPDATE",changes={"title":row.title})); db.commit(); db.refresh(row); return row
def save_certification(db,data,row=None):
    is_new = row is None; row=row or Certification(); faculty_or_422(db,data.faculty_id)
    for key,value in data.model_dump().items(): setattr(row,key,value)
    db.add(row); db.flush(); db.add(CertificationChangeLog(certification_id=row.id,action="CREATE" if is_new else "UPDATE",changes={"name":row.name})); db.commit(); db.refresh(row); return row


def unlink_evidence_file(path: Path):
    """Small seam for safe, testable post-commit evidence cleanup."""
    path.unlink()


def cleanup_fdp_evidence_files(evidence: list[EvidenceFile]):
    """Remove only files whose resolved paths stay below the configured evidence root.

    This intentionally runs after the relational deletion commits. A filesystem
    cannot participate in SQLite's transaction, so cleanup failures are returned
    to the caller for operational follow-up rather than risking unrelated files.
    """
    root = database.EVIDENCE_ROOT.resolve()
    failures = []
    removed = 0
    for item in evidence:
        target = (root / item.storage_path).resolve()
        if not target.is_relative_to(root):
            failures.append({"evidence_id": item.id, "filename": item.original_filename, "reason": "unsafe storage path"})
            continue
        try:
            if target.exists():
                unlink_evidence_file(target)
                removed += 1
        except OSError as exc:
            failures.append({"evidence_id": item.id, "filename": item.original_filename, "reason": str(exc)})
    return removed, failures

@router.get("/fdp-options")
def fdp_options(): return {"activity_types":ACTIVITY_TYPES,"roles":ROLES,"duration_units":("HOURS","DAYS","WEEKS","MONTHS"),"modes":("PHYSICAL","ONLINE","HYBRID")}
@router.get("/fdp-activities")
def list_activities(db:DB,from_date:date|None=None,to_date:date|None=None,activity_type:str|None=None,activity_group:str|None=None,faculty_id:int|None=None,role:str|None=None,search:str|None=None,include_inactive:bool=False,page:int|None=None,page_size:PageSize=25):
    validate_date_range(from_date,to_date,required=False); query=select(FdpActivity)
    if not include_inactive: query=query.where(FdpActivity.is_active.is_(True))
    if from_date: query=query.where(FdpActivity.start_date>=from_date,FdpActivity.start_date<=to_date)
    if activity_type: query=query.where(FdpActivity.activity_type==activity_type)
    if activity_group == "OTHER": query=query.where(FdpActivity.activity_type.not_in(("FDP","WORKSHOP","STTP")))
    if activity_group not in (None,"OTHER"): raise HTTPException(422,"Unknown activity group")
    if faculty_id: query=query.where(FdpActivity.participants.any(FdpParticipant.faculty_id==faculty_id))
    if role: query=query.where(FdpActivity.participants.any(FdpParticipant.role==role))
    if search: query=query.where(or_(FdpActivity.title.ilike(f"%{search}%"),FdpActivity.organizing_institution.ilike(f"%{search}%"),FdpActivity.participants.any(FdpParticipant.faculty_id.in_(select(Faculty.id).where(Faculty.name.ilike(f"%{search}%"))))))
    if page_size != "all" and page_size not in ALLOWED_PAGE_SIZES: raise HTTPException(422,"Page size must be 10, 25, 50 or all")
    if page is not None:
        if page < 1: raise HTTPException(422,"Page must be positive")
        total=db.scalar(select(func.count()).select_from(query.subquery())) or 0
        ordered=query.order_by(FdpActivity.start_date.desc(),FdpActivity.id.desc())
        records=db.scalars(ordered if page_size == "all" else ordered.offset((page-1)*page_size).limit(page_size)).unique().all()
        return {"items":[activity_dict(x,db) for x in records],"total":total,"page":1 if page_size == "all" else page,"page_size":page_size}
    return [activity_dict(x,db) for x in db.scalars(query.order_by(FdpActivity.start_date.desc(),FdpActivity.id.desc())).unique()]
@router.post("/fdp-activities",status_code=201)
def create_activity(data:ActivityInput,db:DB): return activity_dict(save_activity(db,data),db)
@router.get("/fdp-activities/{identity}")
def activity_detail(identity:int,db:DB):
    row=db.get(FdpActivity,identity)
    if not row: raise HTTPException(404,"Activity not found")
    return {**activity_dict(row,db),"change_log":[columns(x) for x in db.scalars(select(FdpChangeLog).where(FdpChangeLog.activity_id==identity).order_by(FdpChangeLog.id.desc()))]}
@router.put("/fdp-activities/{identity}")
def update_activity(identity:int,data:ActivityInput,db:DB):
    row=db.get(FdpActivity,identity)
    if not row: raise HTTPException(404,"Activity not found")
    return activity_dict(save_activity(db,data,row),db)
@router.delete("/fdp-activities/{identity}")
def delete_activity(identity:int,db:DB):
    row=db.get(FdpActivity,identity)
    if not row: raise HTTPException(404,"Activity not found")
    row.is_active=False; db.add(FdpChangeLog(activity_id=identity,action="DEACTIVATE",changes={"is_active":False}));db.commit();return {"id":identity,"is_active":False}


@router.post("/fdp-activities/{identity}/reactivate")
def reactivate_activity(identity:int,db:DB):
    row=db.get(FdpActivity,identity)
    if not row: raise HTTPException(404,"Activity not found")
    if row.is_active: raise HTTPException(409,"Activity is already active")
    row.is_active=True
    db.add(FdpChangeLog(activity_id=identity,action="REACTIVATE",changes={"is_active":True}))
    db.commit()
    db.refresh(row)
    return activity_dict(row,db)


@router.delete("/fdp-activities/{identity}/permanent")
def permanently_delete_activity(identity:int,db:DB):
    row=db.get(FdpActivity,identity)
    if not row: raise HTTPException(404,"Activity not found")

    # Keep file metadata before the row and its activity-owned evidence records
    # are deleted in the transaction below.
    evidence=list(db.scalars(select(EvidenceFile).where(EvidenceFile.fdp_activity_id==identity)))
    try:
        # FdpParticipant, FdpSpeaker, and EvidenceFile are delete-orphan
        # relationships. FdpChangeLog has no ON DELETE cascade, so it must be
        # removed explicitly before deleting the activity.
        db.query(FdpChangeLog).filter(FdpChangeLog.activity_id==identity).delete(synchronize_session=False)
        db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
        raise

    files_removed, cleanup_failures=cleanup_fdp_evidence_files(evidence)
    return {
        "deleted":identity,
        "evidence_files_removed":files_removed,
        "evidence_cleanup_failures":cleanup_failures,
    }

@router.get("/fdp-dashboard")
def fdp_dashboard(db:DB,from_date:date,to_date:date,activity_type:str|None=None,activity_group:str|None=None,faculty_id:int|None=None,role:str|None=None,search:str|None=None,include_inactive:bool=False):
    records=list_activities(db,from_date,to_date,activity_type,activity_group,faculty_id,role,search,include_inactive)
    types={kind:sum(row["activity_type"]==kind for row in records) for kind in ACTIVITY_TYPES}
    participant_counts={}
    for row in records:
        # A Faculty member can hold multiple roles in one activity, but still
        # contributes one distinct activity to this person-level KPI.
        for identity in {p["faculty_id"] for p in row["participants"]}:
            participant_counts[identity]=participant_counts.get(identity,0)+1
    people={person.id:person for person in db.scalars(select(Faculty).where(Faculty.id.in_(participant_counts)))}
    faculty_participants=[
        {"id":identity,"name":people[identity].name,"is_active":people[identity].is_active,"activity_count":count}
        for identity,count in sorted(participant_counts.items(),key=lambda item: people[item[0]].name.lower())
    ]
    role_counts={role_name:sum(p["role"]==role_name for row in records for p in row["participants"]) for role_name in ROLES}
    faculty_performance=[]
    for identity, person in sorted(people.items(), key=lambda item:item[1].name.lower()):
        involved=[row for row in records if any(p["faculty_id"]==identity for p in row["participants"])]
        associations=[p for row in involved for p in row["participants"] if p["faculty_id"]==identity]
        faculty_performance.append({
            "id":identity,"name":person.name,"employee_id":person.employee_id,"activities":len(involved),
            "participations":len(associations),
            **{f"role_{role_name.lower()}":sum(p["role"]==role_name for p in associations) for role_name in ROLES},
            **{f"type_{kind.lower()}":sum(row["activity_type"]==kind for row in involved) for kind in ("FDP","WORKSHOP","STTP")},
        })
    trend=monthly_rows(from_date,to_date,records,"start_date",{
        "activities":lambda row:True,"fdp":lambda row:row["activity_type"]=="FDP",
        "workshops":lambda row:row["activity_type"]=="WORKSHOP","sttp":lambda row:row["activity_type"]=="STTP",
    })
    return {"totals":{"activities":len(records),"faculty_contributors":len(participant_counts),"fdp":types["FDP"],"sttp":types["STTP"],"workshops":types["WORKSHOP"],"webinars":types["WEBINAR"],"seminars":types["SEMINAR"],"internships":types["INTERNSHIP"],"industrial_training":types["INDUSTRIAL_TRAINING"]},"types":types,"role_counts":role_counts,"trend":trend,"faculty_performance":faculty_performance,"faculty_participants":faculty_participants}

@router.get("/certification-options")
def certification_options(): return {"categories":("NPTEL_SWAYAM","MOOC","OTHER"),"statuses":("COMPLETED","IN_PROGRESS")}
@router.get("/certifications")
def list_certifications(db:DB,from_date:date|None=None,to_date:date|None=None,faculty_id:int|None=None,category:str|None=None,status:str|None=None,search:str|None=None,include_inactive:bool=False,page:int|None=None,page_size:PageSize=25,current_in_progress:bool=False):
    validate_date_range(from_date,to_date,required=False); query=select(Certification)
    if not include_inactive: query=query.where(Certification.is_active.is_(True))
    if current_in_progress:
        if status not in (None,"IN_PROGRESS"): raise HTTPException(422,"Current in-progress mode only supports IN_PROGRESS status")
        query=query.where(Certification.status=="IN_PROGRESS")
    elif from_date: query=query.where(Certification.completion_date>=from_date,Certification.completion_date<=to_date)
    if faculty_id: query=query.where(Certification.faculty_id==faculty_id)
    if category: query=query.where(Certification.category==category)
    if status and not current_in_progress: query=query.where(Certification.status==status)
    if search: query=query.where(or_(Certification.name.ilike(f"%{search}%"),Certification.provider.ilike(f"%{search}%"),Certification.faculty_id.in_(select(Faculty.id).where(Faculty.name.ilike(f"%{search}%")))))
    if page_size != "all" and page_size not in ALLOWED_PAGE_SIZES: raise HTTPException(422,"Page size must be 10, 25, 50 or all")
    if page is not None:
        if page < 1: raise HTTPException(422,"Page must be positive")
        total=db.scalar(select(func.count()).select_from(query.subquery())) or 0
        ordered=query.order_by(Certification.completion_date.desc(),Certification.id.desc())
        items=db.scalars(ordered if page_size == "all" else ordered.offset((page-1)*page_size).limit(page_size)).all()
        return {"items":[certification_dict(x,db) for x in items],"total":total,"page":1 if page_size == "all" else page,"page_size":page_size}
    return [certification_dict(x,db) for x in db.scalars(query.order_by(Certification.completion_date.desc(),Certification.id.desc()) )]
@router.post("/certifications",status_code=201)
def create_certification(data:CertificationInput,db:DB): return certification_dict(save_certification(db,data),db)
@router.get("/certifications/{identity}")
def certification_detail(identity:int,db:DB):
    row=db.get(Certification,identity)
    if not row: raise HTTPException(404,"Certification not found")
    return {**certification_dict(row,db),"change_log":[columns(x) for x in db.scalars(select(CertificationChangeLog).where(CertificationChangeLog.certification_id==identity).order_by(CertificationChangeLog.id.desc()))]}
@router.put("/certifications/{identity}")
def update_certification(identity:int,data:CertificationInput,db:DB):
    row=db.get(Certification,identity)
    if not row: raise HTTPException(404,"Certification not found")
    return certification_dict(save_certification(db,data,row),db)
@router.delete("/certifications/{identity}")
def delete_certification(identity:int,db:DB):
    row=db.get(Certification,identity)
    if not row: raise HTTPException(404,"Certification not found")
    row.is_active=False;db.add(CertificationChangeLog(certification_id=identity,action="DEACTIVATE",changes={"is_active":False}));db.commit();return {"id":identity,"is_active":False}

@router.get("/certification-dashboard")
def certification_dashboard(db:DB,from_date:date,to_date:date,faculty_id:int|None=None,category:str|None=None,status:str|None=None,search:str|None=None,include_inactive:bool=False):
    """Return department-wide certification metrics without table pagination.

    Completion is a date-based outcome; in-progress work is a current state.
    Consequently, only completed metrics and category totals are constrained by
    the selected inclusive completion-date range.
    """
    validate_date_range(from_date,to_date,required=True)
    records=list_certifications(
        db,
        faculty_id=faculty_id,
        category=category,
        search=search,
        include_inactive=include_inactive,
    )
    completed=[r for r in records if r["status"]=="COMPLETED" and r["completion_date"] and from_date <= r["completion_date"] <= to_date]
    in_progress=[r for r in records if r["status"]=="IN_PROGRESS"]
    if status == "COMPLETED": in_progress=[]
    elif status == "IN_PROGRESS": completed=[]
    elif status is not None: raise HTTPException(422,"Unknown certification status")
    faculty_ids={r["faculty_id"] for r in completed}|{r["faculty_id"] for r in in_progress}
    faculty={person.id:person for person in db.scalars(select(Faculty).where(Faculty.id.in_(faculty_ids)))}
    faculty_performance=[]
    for identity, person in sorted(faculty.items(),key=lambda item:item[1].name.lower()):
        person_completed=[row for row in completed if row["faculty_id"]==identity]
        person_current=[row for row in in_progress if row["faculty_id"]==identity]
        faculty_performance.append({"id":identity,"name":person.name,"employee_id":person.employee_id,
            "completed":len(person_completed),"nptel_swayam":sum(row["category"]=="NPTEL_SWAYAM" for row in person_completed),"mooc":sum(row["category"]=="MOOC" for row in person_completed),
            "other":sum(row["category"]=="OTHER" for row in person_completed),"in_progress":len(person_current)})
    provider_counts={}
    for row in completed:
        provider_counts[row["provider"]]=provider_counts.get(row["provider"],0)+1
    providers=[{"provider":name,"completed":count} for name,count in sorted(provider_counts.items(),key=lambda item:(-item[1],item[0].lower()))]
    trend=monthly_rows(from_date,to_date,completed,"completion_date",{
        "completed":lambda row:True,"nptel_swayam":lambda row:row["category"]=="NPTEL_SWAYAM","mooc":lambda row:row["category"]=="MOOC",
        "other":lambda row:row["category"]=="OTHER",
    })
    return {
        "totals":{
            "certifications":len(completed),
            "completed":len(completed),
            "in_progress":len(in_progress),
            "faculty_contributors":len({r["faculty_id"] for r in completed}),
        },
        "categories":{kind:sum(r["category"]==kind for r in completed) for kind in ("NPTEL_SWAYAM","MOOC","OTHER")},
        "trend":trend,"providers":providers,"faculty_performance":faculty_performance,
        "records":completed,
        "current_work":in_progress,
    }
