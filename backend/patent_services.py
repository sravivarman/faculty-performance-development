from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from .matching import normalized_name
from .models import Faculty, Patent, PatentChangeLog, PatentInventor, PatentStatusHistory, Student, now
from .patent_schemas import normalize_application_number
from .patent_types import PATENT_TYPES
from .reporting import validate_date_range, within
from .services import columns


def inventor_key(inventor):
    return (inventor.person_type, inventor.faculty_id or inventor.student_id or
            normalized_name(inventor.employee_or_roll_number or inventor.inventor_name))


def indicators(patent):
    local = [i for i in patent.inventors if i.is_current_department]
    other = [i for i in patent.inventors if i.institution_scope == "SAME_INSTITUTION_OTHER_DEPARTMENT"]
    external = [i for i in patent.inventors if i.institution_scope == "EXTERNAL_INSTITUTION" or (i.person_type == "EXTERNAL_PERSON" and i.institution_scope == "UNKNOWN")]
    departments = {normalized_name(i.department_name) for i in patent.inventors if i.is_internal_institution and i.department_name}
    students = {inventor_key(i) for i in local if i.person_type == "STUDENT"}
    faculty = {inventor_key(i) for i in local if i.person_type == "FACULTY"}
    return {"has_current_department_inventor": bool(local),
            "has_multiple_department_inventors": len(departments) > 1,
            "has_same_institution_other_department_inventor": bool(other),
            "has_external_institution_inventor": bool(external),
            "has_current_department_student": bool(students),
            "current_department_faculty_count": len(faculty),
            "current_department_student_count": len(students),
            "same_institution_other_department_count": len(other), "external_inventor_count": len(external)}


def patent_dict(patent, db):
    inventors = []
    for i in patent.inventors:
        person = db.get(Faculty, i.faculty_id) if i.faculty_id else db.get(Student, i.student_id) if i.student_id else None
        inventors.append({**columns(i), "person_name": person.name if person else None,
                          "mapping_status": "CURRENT_DEPARTMENT_UNMATCHED" if i.is_current_department and not i.faculty_id and not i.student_id else i.person_type,
                          "is_current_department": i.is_current_department, "is_internal_institution": i.is_internal_institution})
    return {**columns(patent), **indicators(patent), "inventors": inventors,
            "evidence_count": len(patent.evidence),
            "evidence": [{k:v for k,v in columns(e).items() if k != "storage_path"} for e in patent.evidence],
            "status_history": [columns(h) for h in patent.status_history]}


def save_patent(db, data, patent=None, *, commit=True):
    number = normalize_application_number(data.application_number)
    if number:
        existing = db.scalar(select(Patent).where(Patent.normalized_application_number == number))
        if existing and (not patent or existing.id != patent.id):
            raise HTTPException(409, {"message":"Patent already exists.", "patent_id":existing.id})
    else:
        names = sorted(normalized_name(i.inventor_name) for i in data.inventors)
        year = data.filing_date.year if data.filing_date else None
        duplicates = [p.id for p in db.scalars(select(Patent)) if (not patent or p.id != patent.id)
                      and normalized_name(p.title) == normalized_name(data.title)
                      and (p.filing_date.year if p.filing_date else None) == year
                      and sorted(normalized_name(i.inventor_name) for i in p.inventors) == names]
        if duplicates and not data.duplicate_acknowledged:
            raise HTTPException(409, {"message":"Possible duplicate patent: title, inventor list and filing year match. Review before saving separately.", "possible_duplicate_ids":duplicates})
    for inventor in data.inventors:
        for model, identity in ((Faculty,inventor.faculty_id),(Student,inventor.student_id)):
            if identity:
                person = db.get(model,identity)
                if not person:
                    raise HTTPException(422,f"Unknown {model.__name__} id {identity}")
                if not inventor.employee_or_roll_number:
                    inventor.employee_or_roll_number = person.employee_id if model is Faculty else person.roll_number
    before = patent_dict(patent,db) if patent else None
    old_status = patent.current_status if patent else None
    values = data.model_dump(exclude={"inventors","duplicate_acknowledged","status_note"})
    values["normalized_application_number"] = number
    if patent is None:
        patent = Patent(**values)
        db.add(patent)
        db.flush()
    else:
        for key,value in values.items():
            setattr(patent,key,value)
        patent.inventors.clear()
        db.flush()
        patent.updated_at = now()
    patent.inventors = [PatentInventor(**i.model_dump()) for i in data.inventors]
    if old_status != data.current_status:
        patent.status_history.append(PatentStatusHistory(old_status=old_status,new_status=data.current_status,note=data.status_note))
    db.flush()
    db.add(PatentChangeLog(patent_id=patent.id,action="UPDATE" if before else "CREATE",changes=jsonable_encoder({"before":before,"after":patent_dict(patent,db)})))
    if commit:
        db.commit()
    return patent


def selected_patents(db, current_status=None,patent_type=None, faculty_id=None, student_id=None, student_participation=None,
                     patent_office=None, country=None, include_inactive=False, department_only=True,
                     drill_faculty_id=None, drill_student_id=None):
    query = select(Patent).order_by(Patent.filing_date.desc(),Patent.id.desc())
    if not include_inactive:
        query = query.where(Patent.is_active.is_(True))
    if patent_type:
        query = query.where(Patent.patent_type == patent_type)
    if current_status:
        query = query.where(Patent.current_status == current_status)
    if patent_office:
        query = query.where(Patent.patent_office == patent_office)
    if country:
        query = query.where(Patent.country == country)
    if department_only:
        query = query.where(Patent.inventors.any(PatentInventor.institution_scope == "CURRENT_DEPARTMENT"))
    for identity, column in ((faculty_id,PatentInventor.faculty_id),(student_id,PatentInventor.student_id),
                             (drill_faculty_id,PatentInventor.faculty_id),(drill_student_id,PatentInventor.student_id)):
        if identity:
            query = query.where(Patent.inventors.any(column == identity))
    patents = db.scalars(query).all()
    if student_participation is not None:
        patents = [p for p in patents if indicators(p)["has_current_department_student"] == student_participation]
    return patents


def patent_drilldown(patents, from_date, to_date, metric="unique", claimant_id=None):
    validate_date_range(from_date,to_date)
    field = {"filed":"filing_date", "published":"publication_date", "granted":"grant_date"}.get(metric,"filing_date")
    selected = [p for p in patents if (within(getattr(p,field),from_date,to_date) if metric in ("filed","published","granted") else any(within(getattr(p,event),from_date,to_date) for event in ("filing_date","publication_date","grant_date")))]
    conditions = {
        "unique":lambda p:True,"filed":lambda p:True,"published":lambda p:True,"granted":lambda p:True,
        "missing_evidence":lambda p:not p.evidence,
        "missing_lifecycle":lambda p:(p.current_status in ('PUBLISHED','GRANTED') and not p.publication_date) or (p.current_status == 'GRANTED' and not p.grant_date),
        "with_students":lambda p:indicators(p)["has_current_department_student"],
        "with_confirmed_students":lambda p:any(i.is_current_department and i.person_type == 'STUDENT' and i.student_id is not None for i in p.inventors),
        "unique_faculty":lambda p:indicators(p)["current_department_faculty_count"] > 0,
        "unique_students":lambda p:indicators(p)["current_department_student_count"] > 0,
        "interdepartmental":lambda p:indicators(p)["has_multiple_department_inventors"],
        "external_collaboration":lambda p:indicators(p)["has_external_institution_inventor"],
        "claimed":lambda p:any(i.is_claiming_faculty and (not claimant_id or i.faculty_id == claimant_id) for i in p.inventors),
    }
    if metric not in conditions:
        raise HTTPException(422,"Unknown patent KPI metric")
    return [p for p in selected if conditions[metric](p)]


def patent_type_counts(patents, from_date, to_date):
    selected = patent_drilldown(patents, from_date, to_date)
    return {kind: sum(p.patent_type == kind for p in selected) for kind in PATENT_TYPES}


def patent_kpis(patents,from_date,to_date):
    initiated = patent_drilldown(patents,from_date,to_date)
    return {"unique":len(initiated),
            **{key:len(patent_drilldown(patents,from_date,to_date,key)) for key in ("filed","published","granted","with_students","interdepartmental","external_collaboration")},
            "unique_faculty":len({inventor_key(i) for p in initiated for i in p.inventors if i.is_current_department and i.person_type == "FACULTY"}),
            "unique_students":len({inventor_key(i) for p in initiated for i in p.inventors if i.is_current_department and i.person_type == "STUDENT"})}


def patent_person_kpis(db,patents,from_date,to_date,kind):
    result = []
    model = Faculty if kind == "faculty" else Student
    for person in db.scalars(select(model).order_by(model.name)):
        related = [p for p in patents if any((i.faculty_id if kind == "faculty" else i.student_id) == person.id and i.is_current_department for i in p.inventors)]
        initiated = patent_drilldown(related,from_date,to_date)
        row = {"id":person.id,"name":person.name,"invented":len(initiated),
               **{event:len(patent_drilldown(related,from_date,to_date,event)) for event in ("filed","published","granted")}}
        if kind == "faculty":
            row["claimed"] = len(patent_drilldown(related,from_date,to_date,"claimed",person.id))
        else:
            row["roll_number"] = person.roll_number
            collaborators = {i.faculty_id for p in related for i in p.inventors if i.faculty_id and
                             any(within(getattr(p,field),from_date,to_date) for field in ("filing_date","publication_date","grant_date"))}
            row["faculty_collaborators"] = [{"id":i,"name":db.get(Faculty,i).name} for i in sorted(collaborators)]
        result.append(row)
    return result
