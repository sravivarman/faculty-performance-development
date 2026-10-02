from datetime import date
from typing import Annotated
from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from .db import get_db
from .reporting import validate_date_range
from .services import department_kpis,faculty_kpis,filtered_publications
from .patent_services import patent_kpis,patent_person_kpis,selected_patents
from .book_services import book_kpis,person_kpis,selected_books

router=APIRouter()
DB=Annotated[Session,Depends(get_db)]


@router.get('/research/faculty/{identity}')
def faculty_details(identity:int,db:DB,from_date:date,to_date:date):
    from .dashboard_reporting import faculty_details as details
    return details(db,identity,from_date,to_date)


@router.get("/research/overview")
def research_overview(db:DB,from_date:date,to_date:date,calendar_year:int|None=None,granularity:str|None=None):
    from .research_overview import overview, activity_trend
    if granularity is not None:
        return activity_trend(db,from_date,to_date,calendar_year,granularity)
    return overview(db,from_date,to_date)


@router.get("/research/activities")
def research_activities(db:DB,from_date:date,to_date:date,faculty_id:int|None=None,student_only:bool=False):
    from .research_overview import activities
    validate_date_range(from_date,to_date)
    rows,_,_=activities(db,from_date,to_date)
    return [r for r in rows if (not faculty_id or faculty_id in r['faculty_ids']) and (not student_only or r['student_ids'])]


@router.get("/dashboard-kpis")
def dashboard(db:DB,from_date:date,to_date:date):
    validate_date_range(from_date,to_date)
    publications=department_kpis(filtered_publications(db,from_date=from_date,to_date=to_date))
    patents=patent_kpis(selected_patents(db),from_date,to_date)
    books=book_kpis(selected_books(db,from_date=from_date,to_date=to_date))
    return {"publications":publications["total"],"publications_journal":publications["journal"],"publications_conference":publications["conference"],**{f"patents_{key}":patents[key] for key in ("unique","filed","published","granted")},
            **{f"books_{key}":books[key] for key in ("total","books","chapters")}}


@router.get("/faculty-kpis")
def faculty_dashboard(db:DB,from_date:date,to_date:date):
    validate_date_range(from_date,to_date)
    publications=faculty_kpis(db,filtered_publications(db,from_date=from_date,to_date=to_date))
    patents={p["id"]:p for p in patent_person_kpis(db,selected_patents(db),from_date,to_date,"faculty")}
    books={p["id"]:p for p in person_kpis(db,selected_books(db,from_date=from_date,to_date=to_date),"faculty")}
    return [{"id":p["id"],"name":p["name"],"papers_claimed":p["claimed"],"papers_authored":p["authored"],
             "patents_claimed":patents[p["id"]]["claimed"],"patents_invented":patents[p["id"]]["invented"],
             "books_claimed":books[p["id"]]["claimed"],"books_authored":books[p["id"]]["authored"]} for p in publications]
