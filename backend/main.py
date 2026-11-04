from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import db as database
from .db import get_db, sqlite_database_path
from .doi import normalize_doi, parse_doi_input
from .evidence import permanently_delete_owner
from .matching import match_author
from .name_variants import normalize_person_name, prepare_variants
from .metadata import CrossrefProvider, MetadataError
from .models import (
    AcademicYear,
    BookContributor,
    Certification,
    ChangeLog,
    EvidenceFile,
    Faculty,
    FdpParticipant,
    FundingProjectFaculty,
    PatentInventor,
    Publication,
    PublicationAuthor,
    Student,
    now,
)
from .pagination import PageSize, paginate_records
from .periods import period_options
from .schemas import AuthorInput, FacultyInput, Indexing, PublicationInput, PublicationType, StudentInput, YearInput
from .services import columns, department_kpis, faculty_kpis, filtered_publications, publication_dict, save_publication, student_kpis
from .reporting import validate_date_range

app = FastAPI(title="Faculty publications", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])
DB = Annotated[Session, Depends(get_db)]
provider = CrossrefProvider()


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Conflicting record: DOI, master identifier, author order, or claimant must be unique. Refresh and review."})


@app.exception_handler(ValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def get_publication(db, identity):
    pub = db.get(Publication, identity)
    if not pub:
        raise HTTPException(404, "Publication not found")
    return pub


@app.get("/health")
def health(db: DB):
    return {
        "status": "ok",
        "database_path": sqlite_database_path(db),
        "evidence_path": str(database.EVIDENCE_ROOT.resolve()),
    }


@app.get("/masters")
def masters(db: DB):
    return {"faculty": [faculty_dict(p) for p in db.scalars(select(Faculty).order_by(Faculty.name))],
            "students": [columns(p) for p in db.scalars(select(Student).order_by(Student.name))],
            "academic_years": [columns(p) for p in db.scalars(select(AcademicYear).order_by(AcademicYear.start_date.desc()))]}


def faculty_dict(person):
    return {**columns(person), "weak_name_variants": [v for v in person.name_variants
            if (person.name_variant_strengths or {}).get(normalize_person_name(v)) == "WEAK"]}


def save_master(db, model, data, identity=None):
    obj = db.get(model, identity) if identity else model()
    if obj is None:
        raise HTTPException(404, "Master record not found")
    values = data.model_dump()
    if model is Faculty:
        strengths = data.name_variant_strengths
        if strengths is None:
            keys = {normalize_person_name(v) for v in data.name_variants}
            strengths = {k: v for k, v in (obj.name_variant_strengths or {}).items() if k in keys}
        values["name_variants"], values["name_variant_strengths"] = prepare_variants(data.name_variants, strengths)
    for key, value in values.items():
        setattr(obj, key, value)
    db.add(obj)
    db.commit()
    return faculty_dict(obj) if model is Faculty else columns(obj)


def master_dependencies(db: Session, model, identity: int) -> dict[str, int]:
    """Return real stored references before allowing a Master record to vanish.

    The application deliberately keeps historical person associations intact.
    These explicit counts are both safer and more helpful than relying on a
    late foreign-key failure, particularly on SQLite installations where
    foreign-key enforcement can be configured differently per connection.
    """
    if model is Faculty:
        checks = {
            "publication author associations": (PublicationAuthor, PublicationAuthor.faculty_id),
            "patent inventor associations": (PatentInventor, PatentInventor.faculty_id),
            "book contributor associations": (BookContributor, BookContributor.faculty_id),
            "FDP participant associations": (FdpParticipant, FdpParticipant.faculty_id),
            "certifications": (Certification, Certification.faculty_id),
            "funding investigator associations": (FundingProjectFaculty, FundingProjectFaculty.faculty_id),
        }
    elif model is Student:
        checks = {
            "publication author associations": (PublicationAuthor, PublicationAuthor.student_id),
            "patent inventor associations": (PatentInventor, PatentInventor.student_id),
            "book contributor associations": (BookContributor, BookContributor.student_id),
        }
    elif model is AcademicYear:
        checks = {"publications": (Publication, Publication.academic_year_id)}
    else:  # Defensive guard for future Master types.
        checks = {}
    return {
        label: count
        for label, (dependent, column) in checks.items()
        if (count := db.scalar(select(func.count()).select_from(dependent).where(column == identity)))
    }


def delete_master(db: Session, model, identity: int, description: str):
    record = db.get(model, identity)
    if not record:
        raise HTTPException(404, f"{description} not found")
    dependencies = master_dependencies(db, model, identity)
    if dependencies:
        summary = ", ".join(f"{count} {label}" for label, count in dependencies.items())
        raise HTTPException(409, f"Cannot delete {description}: it is referenced by {summary}.")
    try:
        db.delete(record)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # A future relationship not yet represented above must still never be
        # deleted through a cascade or exposed as a raw database exception.
        raise HTTPException(409, f"Cannot delete {description}: it is referenced by existing records.") from exc
    return {"deleted": identity}


@app.post("/faculty", status_code=201)
def create_faculty(data: FacultyInput, db: DB):
    return save_master(db, Faculty, data)


@app.put("/faculty/{identity}")
def update_faculty(identity: int, data: FacultyInput, db: DB):
    return save_master(db, Faculty, data, identity)


@app.delete("/faculty/{identity}")
def delete_faculty(identity: int, db: DB):
    record = db.get(Faculty, identity)
    description = f"Faculty member {record.name} ({record.employee_id})" if record else "Faculty member"
    return delete_master(db, Faculty, identity, description)


@app.post("/students", status_code=201)
def create_student(data: StudentInput, db: DB):
    return save_master(db, Student, data)


@app.put("/students/{identity}")
def update_student(identity: int, data: StudentInput, db: DB):
    return save_master(db, Student, data, identity)


@app.delete("/students/{identity}")
def delete_student(identity: int, db: DB):
    record = db.get(Student, identity)
    description = f"Student {record.name} ({record.roll_number})" if record else "Student"
    return delete_master(db, Student, identity, description)


@app.post("/academic-years", status_code=201)
def create_year(data: YearInput, db: DB):
    if db.scalar(select(AcademicYear).where(AcademicYear.start_date <= data.end_date, AcademicYear.end_date >= data.start_date)):
        raise HTTPException(409, "Academic years cannot overlap")
    return save_master(db, AcademicYear, data)


@app.put("/academic-years/{identity}")
def update_year(identity: int, data: YearInput, db: DB):
    if not db.get(AcademicYear, identity):
        raise HTTPException(404, "Academic year not found")
    if db.scalar(select(AcademicYear).where(
        AcademicYear.id != identity,
        AcademicYear.start_date <= data.end_date,
        AcademicYear.end_date >= data.start_date,
    )):
        raise HTTPException(409, "Academic years cannot overlap")
    return save_master(db, AcademicYear, data, identity)


@app.delete("/academic-years/{identity}")
def delete_year(identity: int, db: DB):
    record = db.get(AcademicYear, identity)
    description = f"Academic Year {record.name}" if record else "Academic Year"
    return delete_master(db, AcademicYear, identity, description)


@app.get("/academic-years/{identity}/periods")
def periods(identity: int, db: DB, period_type: str = "ACADEMIC_YEAR"):
    year = db.get(AcademicYear, identity)
    if not year:
        raise HTTPException(404, "Academic year not found")
    try:
        return period_options(year, period_type)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/publications/lookup-doi")
def lookup_doi(doi: str, db: DB):
    try:
        doi = normalize_doi(doi)
        if not doi:
            raise ValueError("Enter a DOI")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = db.scalar(select(Publication).where(Publication.doi == doi))
    if existing:
        raise HTTPException(409, {"message": "Publication already exists.", "publication_id": existing.id})
    try:
        result = provider.fetch_by_doi(doi)
    except MetadataError as exc:
        raise HTTPException(502, str(exc)) from exc
    faculty, students = db.scalars(select(Faculty)).all(), db.scalars(select(Student)).all()
    result["authors"] = [match_author(a, faculty, students) for a in result["authors"]]
    return result


from pydantic import BaseModel, Field
from .bibtex import BibTeXPublicationParser


class BibTeXPaste(BaseModel):
    content: str = Field(min_length=1, max_length=250_000)
    enrich_doi: bool = True


class DOIPaste(BaseModel):
    content: str = Field(min_length=1, max_length=250_000)


@app.post("/publications/parse-dois")
def parse_dois(data: DOIPaste):
    return {"entries": parse_doi_input(data.content)}


@app.post("/publications/parse-bibtex")
def parse_bibtex(data: BibTeXPaste, db: DB):
    return BibTeXPublicationParser().parse(data.content, db, provider, data.enrich_doi)


def filters(
    from_date: date | None = None, to_date: date | None = None,
    faculty_id: int | None = None, student_id: int | None = None,
    drill_faculty_id: int | None = None, drill_student_id: int | None = None,
    student_participation: bool | None = None, indexing: Indexing | None = None,
    publication_type: PublicationType | None = None, metric: str | None = None, include_inactive: bool = False,
    claiming_faculty_id: int | None = None, quartile: Literal["Q1", "Q2", "Q3", "Q4", "NOT_APPLICABLE", "UNKNOWN"] | None = None,
    classification: Literal["INTERNATIONAL", "NATIONAL", "OTHER", "UNKNOWN"] | None = None,
    dashboard_only: bool = False,
):
    return locals()


@app.get("/publications")
def list_publications(db: DB, selected: Annotated[dict, Depends(filters)],
                      page: int | None = None, page_size: PageSize = 25):
    return paginate_records(filtered_publications(db, **selected), page, page_size,
                            lambda publication: publication_dict(publication, db))


@app.post("/publications", status_code=201)
def create_publication(data: PublicationInput, db: DB):
    if data.publication_type not in {"JOURNAL", "CONFERENCE"}:
        raise HTTPException(422, "Choose Journal or Conference for a new publication; other source types require manual review")
    return publication_dict(save_publication(db, data), db)


@app.get("/publications/{identity}")
def publication_detail(identity: int, db: DB):
    pub = get_publication(db, identity)
    return {**publication_dict(pub, db), "change_log": [columns(log) for log in db.scalars(select(ChangeLog).where(ChangeLog.publication_id == identity).order_by(ChangeLog.changed_at.desc()))]}


@app.put("/publications/{identity}")
def update_publication(identity: int, data: PublicationInput, db: DB):
    return publication_dict(save_publication(db, data, get_publication(db, identity)), db)


@app.delete("/publications/{identity}")
def deactivate_publication(identity: int, db: DB):
    pub = get_publication(db, identity)
    pub.is_active = False
    db.add(ChangeLog(publication_id=identity, action="DEACTIVATE", changes={"is_active": False}))
    db.commit()
    return {"id": identity, "is_active": False}


@app.post("/publications/{identity}/reactivate")
def reactivate_publication(identity: int, db: DB):
    pub = get_publication(db, identity)
    if pub.is_active:
        raise HTTPException(409, "Publication is already active")
    pub.is_active = True
    db.add(ChangeLog(publication_id=identity, action="REACTIVATE", changes={"is_active": True}))
    db.commit()
    return publication_dict(pub, db)


@app.delete("/publications/{identity}/permanent")
def permanently_delete_publication(identity: int, db: DB):
    """Irreversibly delete only this publication and its owned relations."""
    return permanently_delete_owner(db, get_publication(db, identity), "publication_id", identity, ChangeLog, "publication_id")


@app.put("/publications/{identity}/authors")
def replace_authors(identity: int, data: list[AuthorInput], db: DB):
    pub = get_publication(db, identity)
    payload = {**columns(pub), "authors": [a.model_dump() for a in data], "duplicate_acknowledged": True}
    return publication_dict(save_publication(db, PublicationInput.model_validate(payload), pub), db)


@app.get("/publication-kpis")
def kpis(db: DB, selected: Annotated[dict, Depends(filters)]):
    validate_date_range(selected["from_date"],selected["to_date"])
    return department_kpis(filtered_publications(db, **selected))


@app.get("/publication-dashboard")
def publication_dashboard(db: DB, selected: Annotated[dict, Depends(filters)]):
    from .publication_reporting import dashboard
    return dashboard(db, selected)


@app.get("/publication-kpis/faculty")
def faculty_report(db: DB, selected: Annotated[dict, Depends(filters)]):
    validate_date_range(selected["from_date"],selected["to_date"])
    return faculty_kpis(db, filtered_publications(db, **selected))


@app.get("/publication-kpis/students")
def student_report(db: DB, selected: Annotated[dict, Depends(filters)]):
    validate_date_range(selected["from_date"],selected["to_date"])
    return student_kpis(db, filtered_publications(db, **selected))



from .evidence import router as evidence_router
from .patent_api import router as patent_router
from .dashboard_api import router as dashboard_router
from .book_api import router as book_router
from .fdp_certification_api import router as fdp_certification_router
from .funding_api import router as funding_router
from .nba_reporting_api import router as nba_reporting_router
from .publication_reports import router as publication_report_router
app.include_router(patent_router)
app.include_router(publication_report_router)
app.include_router(book_router)
app.include_router(fdp_certification_router)
app.include_router(funding_router)
app.include_router(nba_reporting_router)
app.include_router(dashboard_router)
app.include_router(evidence_router)
