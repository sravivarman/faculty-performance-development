from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import db as database
from .db import get_db, sqlite_database_path
from .doi import normalize_doi, parse_doi_input
from .matching import match_author
from .name_variants import normalize_person_name, prepare_variants
from .metadata import CrossrefProvider, MetadataError
from .models import AcademicYear, ChangeLog, EvidenceFile, Faculty, Publication, Student, now
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
    return {"status": "ok", "database_path": sqlite_database_path(db)}


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


@app.post("/faculty", status_code=201)
def create_faculty(data: FacultyInput, db: DB):
    return save_master(db, Faculty, data)


@app.put("/faculty/{identity}")
def update_faculty(identity: int, data: FacultyInput, db: DB):
    return save_master(db, Faculty, data, identity)


@app.post("/students", status_code=201)
def create_student(data: StudentInput, db: DB):
    return save_master(db, Student, data)


@app.put("/students/{identity}")
def update_student(identity: int, data: StudentInput, db: DB):
    return save_master(db, Student, data, identity)


@app.post("/academic-years", status_code=201)
def create_year(data: YearInput, db: DB):
    if db.scalar(select(AcademicYear).where(AcademicYear.start_date <= data.end_date, AcademicYear.end_date >= data.start_date)):
        raise HTTPException(409, "Academic years cannot overlap")
    return save_master(db, AcademicYear, data)


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
def list_publications(db: DB, selected: Annotated[dict, Depends(filters)]):
    return [publication_dict(p, db) for p in filtered_publications(db, **selected)]


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
app.include_router(patent_router)
app.include_router(book_router)
app.include_router(dashboard_router)
app.include_router(evidence_router)
