import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend.patent_schemas import normalize_application_number
from conftest import paper,report


def inventor(order,kind="FACULTY",identity=None,claim=False,scope="CURRENT_DEPARTMENT",name=None,department=None):
    return {"inventor_order":order,"inventor_name":name or f"{kind} {identity or order}","person_type":kind,
            "institution_scope":scope,"faculty_id":identity if kind=="FACULTY" else None,
            "student_id":identity if kind=="STUDENT" else None,"is_claiming_faculty":claim,
            "department_name":department,"institution_name":"IIT Hyderabad" if scope=="EXTERNAL_INSTITUTION" else None}


def patent(number="ABC123"):
    return {"title":"Efficient energy system","application_number":number,"patent_office":"Indian Patent Office","country":"India","patent_type":"UTILITY",
            "current_status":"GRANTED","filing_date":"2026-08-10","publication_date":"2026-12-15","grant_date":"2027-08-12",
            "inventors":[inventor(1,identity=1,claim=True),inventor(2,identity=2),inventor(3,"STUDENT",1)]}


@pytest.mark.parametrize("value",["ABC123","abc123"," Abc 123 ","abc-123","ABC/123","ABC.123","ABC_123"])
def test_application_normalization(value):
    assert normalize_application_number(value)=="ABC123"


def test_application_duplicate_and_link(setup):
    client,_,_=setup
    first=client.post("/patents",json=patent())
    assert first.status_code==201,first.text
    duplicate=client.post("/patents",json=patent("abc-123"))
    assert duplicate.status_code==409
    assert duplicate.json()["detail"]["patent_id"]==first.json()["id"]


def test_patent_counting_lifecycle_and_people(setup):
    client,_,_=setup
    p1=client.post("/patents",json=patent())
    assert p1.status_code==201,p1.text
    query="/patent-kpis?from_date=2026-07-01&to_date=2027-06-30"
    k=client.get(query).json()
    assert {key:k[key] for key in ["unique","filed","published","granted","with_students"]}=={"unique":1,"filed":1,"published":1,"granted":0,"with_students":1}
    assert [(p["claimed"],p["invented"]) for p in report(client,"/patent-kpis/faculty").json()]==[(1,1),(0,1)]
    assert report(client,"/patent-kpis/students").json()[0]["invented"]==1
    next_year=client.get("/patent-kpis?from_date=2027-07-01&to_date=2028-06-30").json()
    assert next_year["unique"]==1 and next_year["filed"]==0 and next_year["published"]==0 and next_year["granted"]==1
    second=patent("P2");second.update(title="Another patent",filing_date="2026-09-20",publication_date=None,grant_date=None,current_status="FILED",inventors=[inventor(1,identity=2,claim=True),inventor(2,"STUDENT",2)])
    assert client.post("/patents",json=second).status_code==201
    k=client.get(query).json()
    assert k["unique"]==2 and k["unique_faculty"]==2 and k["unique_students"]==2
    f=report(client,"/patent-kpis/faculty").json()
    assert [(p["claimed"],p["invented"]) for p in f]==[(1,1),(1,2)]
    assert [p["invented"] for p in report(client,"/patent-kpis/students").json()]==[1,1]
    rows=client.get("/patents?from_date=2027-07-01&to_date=2028-06-30&metric=granted").json()
    assert [p["id"] for p in rows]==[p1.json()["id"]]
    f=client.get("/patent-kpis/faculty?from_date=2027-07-01&to_date=2028-06-30").json()
    assert f[0]["invented"]==1 and f[0]["granted"]==1


def test_affiliations_and_department_exclusion(setup):
    client,_,_=setup
    payload=patent()
    payload["inventors"]=[inventor(1,identity=1,claim=True),inventor(2,"FACULTY",scope="SAME_INSTITUTION_OTHER_DEPARTMENT",department="ECE",name="Other ECE Faculty"),inventor(3,"FACULTY",scope="SAME_INSTITUTION_OTHER_DEPARTMENT",department="CSE",name="Other CSE Faculty"),inventor(4,"STUDENT",1),inventor(5,"EXTERNAL_PERSON",scope="EXTERNAL_INSTITUTION",name="External inventor")]
    response=client.post("/patents",json=payload)
    assert response.status_code==201,response.text
    p=response.json()
    assert p["current_department_faculty_count"]==1
    assert p["current_department_student_count"]==1
    assert p["same_institution_other_department_count"]==2
    assert p["external_inventor_count"]==1
    assert p["has_multiple_department_inventors"] and p["has_external_institution_inventor"] and p["has_current_department_student"]
    assert p["inventors"][1]["institution_name"]=="Vardhaman College of Engineering"
    assert p["inventors"][1]["faculty_id"] is None
    outsider=patent("OUTSIDE");outsider["inventors"]=[inventor(1,"FACULTY",scope="SAME_INSTITUTION_OTHER_DEPARTMENT",department="CSE")]
    assert client.post("/patents",json=outsider).status_code==201
    k=report(client,"/patent-kpis").json()
    assert k["unique"]==1 and k["unique_faculty"]==1 and k["interdepartmental"]==1 and k["external_collaboration"]==1
    assert len(client.get("/patents?department_only=false").json())==2
    assert report(client,"/patent-kpis/faculty").json()[1]["invented"]==0


@pytest.mark.parametrize("case",["other_department_claimant","student_claimant","unknown_faculty","wrong_master_scope","no_claimant","nonclaimable","duplicate_student"])
def test_claim_and_mapping_validation(setup,case):
    client,_,_=setup
    p=patent()
    if case=="other_department_claimant":p["inventors"][0].update(institution_scope="SAME_INSTITUTION_OTHER_DEPARTMENT",department_name="CSE",faculty_id=None)
    if case=="student_claimant":p["inventors"][2]["is_claiming_faculty"]=True
    if case=="unknown_faculty":p["inventors"][0]["faculty_id"]=999
    if case=="wrong_master_scope":p["inventors"][1].update(institution_scope="EXTERNAL_INSTITUTION",institution_name="IIT")
    if case=="no_claimant":p["inventors"][0]["is_claiming_faculty"]=False
    if case=="nonclaimable":p["is_claimable"]=False
    if case=="duplicate_student":p["inventors"].append(inventor(4,"STUDENT",1))
    response=client.post("/patents",json=p)
    assert response.status_code==422,response.text


def test_database_patent_claim_rules(setup):
    client,factory,_=setup
    p=client.post("/patents",json=patent()).json()
    with factory() as db:
        for sql in [
                    "UPDATE patent_inventors SET institution_scope='EXTERNAL_INSTITUTION' WHERE faculty_id=1",
                    "UPDATE patent_inventors SET is_claiming_faculty=1 WHERE student_id=1"]:
            with pytest.raises(IntegrityError):db.execute(text(sql))
            db.rollback()
    assert client.get(f"/patents/{p['id']}").json()["inventors"][0]["is_claiming_faculty"]


def test_lifecycle_edit_same_record_status_history(setup):
    client,_,_=setup
    payload=patent();payload.update(current_status="FILED",publication_date=None,grant_date=None)
    first=client.post("/patents",json=payload).json()
    identity=first["id"]
    payload.update(current_status="PUBLISHED",publication_date="2026-12-15",publication_number="PUB123",status_note="Publication confirmed")
    second=client.put(f"/patents/{identity}",json=payload)
    assert second.status_code==200,second.text
    payload.update(current_status="GRANTED",grant_date="2027-08-12",grant_number="GR123",status_note="Grant certificate received")
    third=client.put(f"/patents/{identity}",json=payload).json()
    assert third["id"]==identity and third["filing_date"]==first["filing_date"] and third["publication_date"]=="2026-12-15"
    assert third["created_at"]==first["created_at"]
    assert [h["new_status"] for h in third["status_history"]]==["FILED","PUBLISHED","GRANTED"]
    assert len(client.get("/patents").json())==1
    assert len(client.get(f"/patents/{identity}").json()["change_log"])==3


def test_early_entry_warning_and_undated_registry(setup):
    client,_,_=setup
    payload=patent(None);payload.update(filing_date=None,publication_date=None,grant_date=None,current_status="OTHER")
    first=client.post("/patents",json=payload)
    assert first.status_code==201
    duplicate=client.post("/patents",json=payload)
    assert duplicate.status_code==409
    assert duplicate.json()["detail"]["possible_duplicate_ids"]==[first.json()["id"]]
    assert report(client,"/patent-kpis").json()["unique"]==0
    assert len(client.get("/patents").json())==1
    payload["duplicate_acknowledged"]=True
    assert client.post("/patents",json=payload).status_code==201


def test_patent_evidence_and_owner_isolation(setup):
    client,factory,tmp=setup
    patent_id=client.post("/patents",json=patent()).json()["id"]
    publication_id=client.post("/publications",json=paper()).json()["id"]
    for category in ["FILING_PROOF","PUBLICATION_PROOF","GRANT_PROOF","OTHER"]:
        response=client.post(f"/patents/{patent_id}/evidence",files={"file":("proof.pdf",b"%PDF-1.4 proof","application/pdf")},data={"evidence_type":category})
        assert response.status_code==201,response.text
    evidence=response.json()
    assert client.get(f"/patents/{patent_id}").json()["evidence_count"]==4
    assert len(list((tmp/"evidence"/"2026-27"/"PATENT"/str(patent_id)).glob("*.pdf")))==4
    assert client.get(f"/publications/{publication_id}/evidence/{evidence['id']}").status_code==404
    assert client.get(f"/patents/{patent_id}/evidence/{evidence['id']}?download=true").status_code==200
    with factory() as db:
        with pytest.raises(IntegrityError):db.execute(text("UPDATE evidence_files SET publication_id=:id"),{"id":publication_id})
        db.rollback()


@pytest.mark.parametrize("path",["/publication-kpis","/publication-kpis/faculty","/publication-kpis/students","/patent-kpis","/patent-kpis/faculty","/patent-kpis/students","/dashboard-kpis","/faculty-kpis"])
def test_date_range_validation_consistent(setup,path):
    client,_,_=setup
    assert client.get(path).status_code==422
    assert client.get(path+"?from_date=2026-09-01").status_code==422
    assert client.get(path+"?from_date=2026-09-30&to_date=2026-09-01").status_code==422
    assert client.get(path+"?from_date=2026-09-01&to_date=2026-09-01").status_code==200


def test_date_boundaries_no_academic_year_and_event_dates(setup):
    client,_,_=setup
    for suffix,day in [("before","2030-08-31"),("start","2030-09-01"),("end","2030-09-30"),("after","2030-10-01")]:
        response=client.post("/publications",json=paper(f"10.1234/{suffix}",day))
        assert response.status_code==201
        assert response.json()["academic_year_id"] is None
    query="from_date=2030-09-01&to_date=2030-09-30"
    assert client.get(f"/publication-kpis?{query}").json()["total"]==2
    assert client.get(f"/publication-kpis/faculty?{query}").json()[0]["claimed"]==2
    assert client.get(f"/publication-kpis/students?{query}").json()[0]["authored"]==2
    assert client.get("/publication-kpis?from_date=2030-09-01&to_date=2030-09-01").json()["total"]==1
    payload=patent();payload.update(filing_date="2030-09-01",publication_date="2030-09-30",grant_date="2030-10-01")
    assert client.post("/patents",json=payload).status_code==201
    counts=client.get(f"/patent-kpis?{query}").json()
    assert counts["filed"]==1 and counts["published"]==1 and counts["granted"]==0
    for metric in ["filed","published","granted"]:
        assert len(client.get(f"/patents?{query}&metric={metric}").json())==counts[metric]
    assert client.get("/patent-kpis?from_date=2030-10-01&to_date=2030-10-01").json()["granted"]==1


def test_combined_dashboard_and_filtered_drilldowns(setup):
    client,_,_=setup
    client.post("/publications",json=paper())
    client.post("/patents",json=patent())
    assert report(client,"/dashboard-kpis").json()=={"publications":1,"publications_journal":1,"publications_conference":0,"patents_unique":1,"patents_filed":1,"patents_published":1,"patents_granted":1,"books_total":0,"books_books":0,"books_chapters":0}
    faculty=report(client,"/faculty-kpis").json()
    assert faculty[0]["papers_claimed"]==1 and faculty[0]["patents_claimed"]==1
    assert faculty[1]["patents_claimed"]==0 and faculty[1]["patents_invented"]==1
    assert report(client,"/patents?faculty_id=1&drill_faculty_id=2&metric=claimed").json()==[]
    assert len(report(client,"/patents?faculty_id=1&drill_faculty_id=2&metric=unique").json())==1
