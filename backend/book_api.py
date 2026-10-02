from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .affiliations import CURRENT_DEPARTMENT, INSTITUTION_NAME
from .book_schemas import BookInput, WorkType
from .book_queue import BookPreviewInput, validate_preview
from .book_services import book_dict, book_kpis, drilldown, person_kpis, save_book, selected_books
from .db import get_db
from .doi import normalize_doi
from .metadata import CrossrefProvider, MetadataError
from .models import BookPublication, BookChangeLog
from .reporting import validate_date_range
from .services import columns

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
provider = CrossrefProvider()


@router.post('/book-preview-validation')
def validate_queue_item(data: BookPreviewInput, db: DB):
    return validate_preview(db, data.draft, data.type_resolved)


@router.get("/book-metadata")
def metadata(doi: str, db: DB):
    try:
        normalized = normalize_doi(doi)
        if not normalized:
            raise ValueError("Enter a DOI to fetch metadata")
        existing = db.scalar(select(BookPublication).where(BookPublication.doi == normalized))
        if existing:
            raise HTTPException(409, {"message": "A Book / Chapter with this DOI already exists.", "book_id": existing.id})
        data = provider.fetch_by_doi(normalized)
        from .book_metadata import book_preview
        return book_preview(data, db)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except MetadataError as exc:
        raise HTTPException(502, str(exc)) from exc


def filters(from_date: date | None = None, to_date: date | None = None, work_type: WorkType | None = None,
            faculty_id: int | None = None, student_id: int | None = None, student_participation: bool | None = None,
            interdepartmental: bool | None = None, external_collaboration: bool | None = None,
            publisher: str | None = None, isbn_search: str | None = None, include_inactive: bool = False):
    validate_date_range(from_date, to_date, required=False)
    return locals()


def get_book(db, identity):
    work = db.get(BookPublication, identity)
    if not work:
        raise HTTPException(404, "Book / chapter not found")
    return work


@router.get("/book-options")
def options(db: DB):
    return {"current_department": CURRENT_DEPARTMENT, "institution_name": INSTITUTION_NAME,
            "publishers": list(db.scalars(select(BookPublication.publisher).distinct().order_by(BookPublication.publisher)))}


@router.post("/books", status_code=201)
def create(data: BookInput, db: DB):
    return persist(data, db)


def persist(data, db, work=None):
    try:
        return book_dict(save_book(db, data, work), db)
    except IntegrityError:
        # The unique DOI index also protects simultaneous saves after preview.
        db.rollback()
        existing = db.scalar(select(BookPublication).where(BookPublication.doi == data.doi)) if data.doi else None
        if existing:
            raise HTTPException(409, {"message": "A Book / Chapter with this DOI already exists.", "book_id": existing.id})
        raise


@router.get("/books")
def records(db: DB, selected: Annotated[dict, Depends(filters)], metric: str = "total",
            department_only: bool = True, drill_faculty_id: int | None = None, drill_student_id: int | None = None):
    return [book_dict(w, db) for w in drilldown(selected_books(db, **selected, department_only=department_only),
                                               metric, drill_faculty_id, drill_student_id)]


@router.get("/books/{identity}")
def detail(identity: int, db: DB):
    return {**book_dict(get_book(db, identity), db),
            "change_log": [columns(c) for c in db.scalars(select(BookChangeLog).where(BookChangeLog.book_record_id == identity).order_by(BookChangeLog.id.desc()))]}


@router.put("/books/{identity}")
def update(identity: int, data: BookInput, db: DB):
    return persist(data, db, get_book(db, identity))


@router.delete("/books/{identity}")
def deactivate(identity: int, db: DB):
    work = get_book(db, identity)
    work.is_active = False
    db.add(BookChangeLog(book_record_id=identity, action="DEACTIVATE", changes={"is_active": False}))
    db.commit()
    return {"id": identity, "is_active": False}


def reporting_books(db, selected):
    validate_date_range(selected["from_date"], selected["to_date"])
    return selected_books(db, **selected)


@router.get("/book-kpis")
def department_report(db: DB, selected: Annotated[dict, Depends(filters)]):
    return book_kpis(reporting_books(db, selected))


@router.get('/book-dashboard')
def dashboard_report(db: DB, selected: Annotated[dict, Depends(filters)], from_date: date, to_date: date):
    from .dashboard_reporting import books_dashboard
    return books_dashboard(db,from_date,to_date,{k:v for k,v in selected.items() if k not in ('from_date','to_date')})


@router.get("/book-kpis/faculty")
def faculty_report(db: DB, selected: Annotated[dict, Depends(filters)]):
    return person_kpis(db, reporting_books(db, selected), "faculty")


@router.get("/book-kpis/students")
def student_report(db: DB, selected: Annotated[dict, Depends(filters)]):
    return person_kpis(db, reporting_books(db, selected), "students")
