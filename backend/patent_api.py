from datetime import date
import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Patent, PatentChangeLog
from .patent_schemas import CURRENT_DEPARTMENT, INSTITUTION_NAME, InventorInput, PatentInput, PatentStatus
from .patent_types import PatentType, PATENT_TYPES
from .patent_services import patent_dict, patent_drilldown, patent_kpis, patent_person_kpis, save_patent, selected_patents
from .reporting import validate_date_range
from .services import columns

router = APIRouter()
DB = Annotated[Session,Depends(get_db)]


def get_patent(db,identity):
    patent = db.get(Patent,identity)
    if not patent:
        raise HTTPException(404,"Patent not found")
    return patent


def patent_filters(patent_type:PatentType|None=None,current_status:PatentStatus|None=None,faculty_id:int|None=None,student_id:int|None=None,
                   student_participation:bool|None=None,patent_office:str|None=None,country:str|None=None,
                   include_inactive:bool=False,drill_faculty_id:int|None=None,drill_student_id:int|None=None):
    return locals()


@router.get("/patent-options")
def patent_options(db:DB):
    return {"institution_name":INSTITUTION_NAME,"current_department":CURRENT_DEPARTMENT,"patent_types":PATENT_TYPES,
            "offices":list(db.scalars(select(Patent.patent_office).distinct().order_by(Patent.patent_office))),
            "countries":list(db.scalars(select(Patent.country).where(Patent.country.is_not(None)).distinct().order_by(Patent.country)))}


@router.post("/patents",status_code=201)
def create_patent(data:PatentInput,db:DB):
    return patent_dict(save_patent(db,data),db)


@router.get("/patents")
def list_patents(db:DB,selected:Annotated[dict,Depends(patent_filters)],from_date:date|None=None,to_date:date|None=None,metric:str|None=None,department_only:bool=True):
    date_range = validate_date_range(from_date,to_date,required=bool(metric))
    patents = selected_patents(db,**selected,department_only=department_only)
    if date_range:
        patents = patent_drilldown(patents,*date_range,metric or "unique",selected.get("drill_faculty_id") or selected.get("faculty_id"))
    return [patent_dict(p,db) for p in patents]


@router.get('/patent-export')
def export_patents(db:DB,selected:Annotated[dict,Depends(patent_filters)],from_date:date|None=None,to_date:date|None=None,metric:str|None=None,department_only:bool=True):
    records = list_patents(db,selected,from_date,to_date,metric,department_only)
    output = io.StringIO(newline='')
    fields = ['id','title','application_number','patent_type','patent_type_label','current_status','filing_date','publication_date','grant_date','inventors','claimants']
    writer = csv.DictWriter(output,fieldnames=fields)
    writer.writeheader()
    for record in records:
        row = {key:record.get(key) for key in fields}
        row['patent_type_label'] = PATENT_TYPES.get(record['patent_type'],'Not configured')
        row['inventors'] = '; '.join(i['inventor_name'] for i in record['inventors'])
        row['claimants'] = '; '.join(i['person_name'] or i['inventor_name'] for i in record['inventors'] if i['is_claiming_faculty'])
        # Keep spreadsheet applications from evaluating user-entered cells.
        writer.writerow({key:"'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value for key,value in row.items()})
    return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="patents.csv"'})


@router.get("/patents/{identity}")
def patent_detail(identity:int,db:DB):
    return {**patent_dict(get_patent(db,identity),db),"change_log":[columns(c) for c in db.scalars(select(PatentChangeLog).where(PatentChangeLog.patent_id==identity).order_by(PatentChangeLog.id.desc()))]}


@router.put("/patents/{identity}")
def update_patent(identity:int,data:PatentInput,db:DB):
    return patent_dict(save_patent(db,data,get_patent(db,identity)),db)


@router.put("/patents/{identity}/inventors")
def update_inventors(identity:int,data:list[InventorInput],db:DB):
    patent = get_patent(db,identity)
    payload = {**columns(patent),"inventors":[i.model_dump() for i in data],"duplicate_acknowledged":True}
    return patent_dict(save_patent(db,PatentInput.model_validate(payload),patent),db)


@router.delete("/patents/{identity}")
def deactivate_patent(identity:int,db:DB):
    patent = get_patent(db,identity);patent.is_active = False
    db.add(PatentChangeLog(patent_id=identity,action="DEACTIVATE",changes={"is_active":False}))
    db.commit()
    return {"id":identity,"is_active":False}


@router.get("/patent-kpis")
def department_report(db:DB,selected:Annotated[dict,Depends(patent_filters)],from_date:date,to_date:date):
    validate_date_range(from_date,to_date)
    return patent_kpis(selected_patents(db,**selected),from_date,to_date)


@router.get('/patent-dashboard')
def dashboard_report(db:DB,selected:Annotated[dict,Depends(patent_filters)],from_date:date,to_date:date):
    from .dashboard_reporting import patents_dashboard
    return patents_dashboard(db,from_date,to_date,selected)


@router.get("/patent-kpis/faculty")
def faculty_report(db:DB,selected:Annotated[dict,Depends(patent_filters)],from_date:date,to_date:date):
    validate_date_range(from_date,to_date)
    return patent_person_kpis(db,selected_patents(db,**selected),from_date,to_date,"faculty")


@router.get("/patent-kpis/students")
def student_report(db:DB,selected:Annotated[dict,Depends(patent_filters)],from_date:date,to_date:date):
    validate_date_range(from_date,to_date)
    return patent_person_kpis(db,selected_patents(db,**selected),from_date,to_date,"students")
