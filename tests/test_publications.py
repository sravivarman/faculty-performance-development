from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.doi import normalize_doi
from backend.main import app
from backend.matching import match_author
from backend.metadata import MetadataError, parse_crossref
from backend.models import AcademicYear, Faculty, Publication, PublicationAuthor, Student
from backend.periods import period_bounds
from conftest import author, paper, report


@pytest.mark.parametrize("value", ["10.1234/Example.123", "https://doi.org/10.1234/example.123", "http://dx.doi.org/10.1234/Example.123", "DOI:10.1234/EXAMPLE.123", " https://doi.org/10.1234%2Fexample.123 "])
def test_doi_normalization(value):
    assert normalize_doi(value) == "10.1234/example.123"


@pytest.mark.parametrize("value", ["bad", "https://example.com/10.1234/paper", "10.12/x", "10.1234/has space"])
def test_bad_doi(value):
    with pytest.raises(ValueError):
        normalize_doi(value)


def test_missing_doi():
    assert normalize_doi("") is None
    assert normalize_doi(None) is None


def test_metadata_parsing():
    raw = {"message": {"DOI": "10.1234/PAPER", "title": ["A study"], "type": "proceedings-article", "container-title": ["Conference"], "publisher": "Publisher", "published": {"date-parts": [[2026,9,18]]}, "published-online": {"date-parts": [[2026,9,10]]}, "published-print": {"date-parts": [[2026,10,1]]}, "volume": "8", "issue": "2", "article-number": "123", "issn-type": [{"type":"print","value":"1111-1111"},{"type":"electronic","value":"2222-2222"}], "ISBN": ["123"], "URL": "https://doi.org/10.1234/PAPER", "author": [{"given":"A","family":"Faculty","ORCID":"https://orcid.org/0000-0001-2345-6789","affiliation":[{"name":"Institute"}]},{"name":"Research Consortium"}]}}
    parsed = parse_crossref(raw, "10.1234/paper")
    assert parsed["publication_type"] == "CONFERENCE"
    assert parsed["publication_date"] == "2026-09-18"
    assert parsed["online_publication_date"] == "2026-09-10"
    assert parsed["print_publication_date"] == "2026-10-01"
    assert parsed["eissn"] == "2222-2222"
    assert parsed["pages_or_article_number"] == "123"
    assert parsed["authors"][0]["affiliation_from_source"] == ["Institute"]
    assert parsed["authors"][1]["author_order"] == 2
    assert parsed["raw_metadata_json"] == raw
    assert parsed["metadata_fetched_at"]
    assert parsed["indexing"] == []


def test_sparse_metadata_and_partial_dates():
    parsed = parse_crossref({"message":{"published":{"date-parts":[[2026,9]]}}}, "10.1234/x")
    assert parsed["publication_date"] is None
    assert parsed["authors"] == []
    assert parsed["title"] == ""
    assert parsed["metadata_source"] == "CROSSREF"


@pytest.mark.parametrize("name,orcid,kind,identity", [
    ("Entirely different name","https://orcid.org/0000-0001-2345-6789","FACULTY",1),
    ("A. Faculty",None,"FACULTY",1), ("X. Student",None,"STUDENT",1), ("Student Y",None,"STUDENT",2),
])
def test_author_matching(setup,name,orcid,kind,identity):
    _, factory, _ = setup
    with factory() as db:
        result = match_author({"author_name_from_source":name,"orcid_from_source":orcid}, db.scalars(select(Faculty)).all(), db.scalars(select(Student)).all())
    assert result["matching_status"] == "EXACT"
    assert result["person_type"] == kind
    assert result["faculty_id" if kind == "FACULTY" else "student_id"] == identity


def test_fuzzy_and_ambiguous_matches_are_not_confirmed(setup):
    _, factory, _ = setup
    with factory() as db:
        faculty = db.scalars(select(Faculty)).all()
        result = match_author({"author_name_from_source":"Faculty Aa"}, faculty, [])
        assert result["matching_status"] == "SUGGESTED"
        assert result.get("faculty_id") is None
        faculty[1].name = faculty[0].name
        result = match_author({"author_name_from_source":"Faculty A"}, faculty, [])
        assert result["matching_status"] == "SUGGESTED"
        assert result.get("faculty_id") is None


def test_orcid_priority_and_conflict(setup):
    _, factory, _ = setup
    with factory() as db:
        faculty = db.scalars(select(Faculty)).all()
        result = match_author({"author_name_from_source":"Faculty B","orcid_from_source":"0000-0001-2345-6789"},faculty,[])
        assert result["faculty_id"] == 1
        result = match_author({"author_name_from_source":"Faculty A","orcid_from_source":"0000-0009-9999-9999"},faculty[:1],[])
        assert not result.get("faculty_id")


def test_duplicate_doi_case_insensitive_even_when_inactive(setup):
    client, _, _ = setup
    first = client.post("/publications",json=paper()).json()
    duplicate = client.post("/publications",json=paper("HTTPS://DOI.ORG/10.1234/P1"))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["publication_id"] == first["id"]
    client.delete(f"/publications/{first['id']}")
    assert client.post("/publications",json=paper()).status_code == 409
    assert report(client,"/publication-kpis").json()["total"] == 0


@pytest.mark.parametrize("case", ["two_claimants","student_claimant","external_claimant","missing_faculty","no_claimant","nonclaimable_claimant","duplicate_faculty","suggested_mapping","unknown_person"])
def test_author_validation(setup,case):
    client,_,_ = setup
    payload = paper()
    if case == "two_claimants": payload["authors"][1]["is_claiming_faculty"] = True
    if case == "student_claimant": payload["authors"][2]["is_claiming_faculty"] = True
    if case == "external_claimant": payload["authors"][3]["is_claiming_faculty"] = True
    if case == "missing_faculty": payload["authors"][0]["faculty_id"] = None
    if case == "no_claimant": payload["authors"][0]["is_claiming_faculty"] = False
    if case == "nonclaimable_claimant": payload["is_claimable"] = False
    if case == "duplicate_faculty": payload["authors"][1]["faculty_id"] = 1
    if case == "suggested_mapping": payload["authors"][0]["matching_status"] = "SUGGESTED"
    if case == "unknown_person": payload["authors"][0]["faculty_id"] = 999
    response = client.post("/publications",json=payload)
    assert response.status_code == 422, response.text
    assert report(client,"/publication-kpis").json()["total"] == 0


def test_nonclaimable_and_student_only(setup):
    client,_,_=setup
    payload=paper();payload["is_claimable"]=False;payload["authors"][0]["is_claiming_faculty"]=False
    assert client.post("/publications",json=payload).status_code == 201
    payload=paper("10.1234/student");payload["authors"]=[author(1,"STUDENT",1)]
    assert client.post("/publications",json=payload).status_code == 422
    payload["is_claimable"]=False
    result=client.post("/publications",json=payload)
    assert result.status_code == 201
    assert result.json()["classifications"] == ["Student-only paper"]


def test_p1_p2_counting_examples_and_drilldowns(setup):
    client,_,_=setup
    p1=client.post("/publications",json=paper())
    assert p1.status_code == 201, p1.text
    assert report(client,"/publication-kpis").json()["total"] == 1
    f=report(client,"/publication-kpis/faculty").json()
    assert [(r["claimed"],r["authored"]) for r in f] == [(1,1),(0,1)]
    assert report(client,"/publication-kpis/students").json()[0]["authored"] == 1
    payload=paper("10.1234/p2");payload["publication_type"]="CONFERENCE";payload["authors"]=[author(1,"FACULTY",2,True),author(2,"STUDENT",1),author(3,"STUDENT",2)]
    assert client.post("/publications",json=payload).status_code == 201
    k=report(client,"/publication-kpis").json()
    assert k == {"total":2,"journal":1,"conference":1,"scopus":2,"web_of_science":0,"sci_scie":2,"with_students":2,"without_students":0,"unique_faculty":2,"unique_students":2,"sci":2,"scie":2,"q1":0,"q2":0,"q3":0,"q4":0,"esci":0,"ugc_care":0,"international_journal":0,"national_journal":0,"international_conference":0,"national_conference":0}
    assert [(r["claimed"],r["authored"]) for r in report(client,"/publication-kpis/faculty").json()] == [(1,1),(1,2)]
    s=report(client,"/publication-kpis/students").json()
    assert [r["authored"] for r in s] == [2,1]
    assert s[0]["journal"] == 1 and s[0]["conference"] == 1 and s[0]["indexed"] == 2
    assert len(s[0]["faculty_collaborators"]) == 2
    for key,count in k.items():
        records=client.get(f"/publications?metric={key}").json()
        if key.startswith("unique"):
            column="faculty_id" if key=="unique_faculty" else "student_id"
            assert len({a[column] for p in records for a in p["authors"] if a[column]}) == count
        else: assert len(records) == count
    assert len(client.get("/publications?faculty_id=2&metric=claimed").json()) == 1
    assert len(client.get("/publications?student_id=1").json()) == 2


@pytest.mark.parametrize("period_type,period,expected", [("MONTHLY",3,1),("MONTHLY",4,1),("QUARTERLY",1,1),("QUARTERLY",2,1),("HALF_YEARLY",1,2),("HALF_YEARLY",2,1),("ACADEMIC_YEAR",1,3)])
def test_period_aggregation(setup,period_type,period,expected):
    client,_,_=setup
    for i,day in enumerate(["2026-09-18","2026-10-01","2027-06-30","2027-07-01"]):
        assert client.post("/publications",json=paper(f"10.1234/{i}",day)).status_code == 201
    from types import SimpleNamespace
    start,end=period_bounds(SimpleNamespace(start_date=date(2026,7,1),end_date=date(2027,6,30)),period_type,period)
    query=f"from_date={start}&to_date={end}"
    assert report(client,f"/publication-kpis?{query}").json()["total"] == expected
    assert len(client.get(f"/publications?{query}").json()) == expected


def test_period_validation_and_options(setup):
    client,_,_=setup
    periods=client.get("/academic-years/1/periods?period_type=MONTHLY").json()
    assert periods[2]["label"] == "September 2026"
    assert client.get("/publication-kpis").status_code == 422
    assert client.get("/publication-kpis?from_date=2026-10-01&to_date=2026-09-01").status_code == 422
    assert report(client,"/publication-kpis?academic_year_id=999").status_code == 200


def test_edit_claimant_date_mapping_and_history(setup):
    client,_,_=setup
    before=client.post("/publications",json=paper()).json()
    payload=paper(publication_date="2027-07-05")
    payload["authors"][0]["is_claiming_faculty"]=False
    payload["authors"][1]["is_claiming_faculty"]=True
    payload["authors"]=[a for a in payload["authors"] if a["person_type"]!="STUDENT"]
    response=client.put(f"/publications/{before['id']}",json=payload)
    assert response.status_code == 200,response.text
    after=response.json()
    assert after["academic_year_id"]==2
    assert after["created_at"]==before["created_at"]
    assert after["updated_at"]!=before["updated_at"]
    assert after["has_internal_students"] is False
    assert after["authors"][1]["is_claiming_faculty"] is True
    assert report(client,"/publication-kpis?from_date=2026-07-01&to_date=2027-06-30").json()["total"]==0
    assert len(client.get(f"/publications/{before['id']}").json()["change_log"])==2
    invalid=client.put(f"/publications/{before['id']}/authors",json=[author(1,"FACULTY",1),author(2,"FACULTY",2)])
    assert invalid.status_code==422


def test_database_enforces_claimant_and_identity(setup):
    client,factory,_=setup
    p=client.post("/publications",json=paper()).json()
    with factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE publication_authors SET is_claiming_faculty=1 WHERE publication_id=:id AND faculty_id=2"),{"id":p["id"]})
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE publication_authors SET is_claiming_faculty=1 WHERE publication_id=:id AND student_id=1"),{"id":p["id"]})
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE publication_authors SET faculty_id=NULL WHERE publication_id=:id AND faculty_id=1"),{"id":p["id"]})
        db.rollback()
        assert db.scalar(select(Publication)).id == p["id"]


def test_no_doi_duplicate_warning(setup):
    client,_,_=setup
    payload=paper(None)
    first=client.post("/publications",json=payload)
    assert first.status_code==201
    response=client.post("/publications",json=payload)
    assert response.status_code==409
    assert response.json()["detail"]["possible_duplicate_ids"]==[first.json()["id"]]
    payload["duplicate_acknowledged"]=True
    assert client.post("/publications",json=payload).status_code==201


def test_lookup_preview_failure_and_duplicate(setup,monkeypatch):
    client,_,_=setup
    from backend import main
    raw={"message":{"DOI":"10.1234/p1","title":["Preview"],"author":[{"name":"A. Faculty"}]}}
    monkeypatch.setattr(main.provider,"fetch_by_doi",lambda doi:parse_crossref(raw,doi))
    response=client.get("/publications/lookup-doi?doi=https://doi.org/10.1234/P1")
    assert response.status_code==200
    assert response.json()["authors"][0]["faculty_id"]==1
    assert client.get("/publications").json()==[]
    def fail(doi): raise MetadataError("Try manual entry")
    monkeypatch.setattr(main.provider,"fetch_by_doi",fail)
    assert client.get("/publications/lookup-doi?doi=10.1234/fail").status_code==502
    assert client.post("/publications",json=paper()).status_code==201
    assert client.get("/publications/lookup-doi?doi=10.1234/P1").status_code==409


def test_evidence_upload_link_view_download_delete(setup):
    client,_,tmp=setup
    pub=client.post("/publications",json=paper()).json()
    identity=pub["id"]
    response=client.post(f"/publications/{identity}/evidence",files={"file":("../../paper.pdf",b"%PDF-1.4\npublication proof","application/pdf")},data={"evidence_type":"PUBLISHED_PAPER"})
    assert response.status_code==201,response.text
    evidence=response.json()
    assert evidence["original_filename"]=="paper.pdf"
    assert "storage_path" not in evidence
    assert list((tmp/"evidence"/"2026-27"/"PAPER"/str(identity)).glob("*.pdf"))
    path=f"/publications/{identity}/evidence/{evidence['id']}"
    assert "inline" in client.get(path).headers["content-disposition"]
    assert "attachment" in client.get(path+"?download=true").headers["content-disposition"]
    assert client.get(f"/publications/{identity}").json()["evidence_count"]==1
    assert client.get(f"/publications/999/evidence/{evidence['id']}").status_code==404
    assert client.post(f"/publications/{identity}/evidence",files={"file":("bad.html",b"<html/>","text/html")}).status_code==422
    assert client.post(f"/publications/{identity}/evidence",files={"file":("empty.pdf",b"","application/pdf")}).status_code==422
    assert client.delete(path).status_code==200
    assert client.get(path).status_code==404
    assert client.get(f"/publications/{identity}").json()["evidence_count"]==0


def test_master_validation_and_year_overlap(setup):
    client,_,_=setup
    assert client.post("/faculty",json={"employee_id":"C","name":"Faculty C","orcid":"https://orcid.org/0000-0002-1234-5678"}).json()["orcid"]=="0000-0002-1234-5678"
    assert client.post("/faculty",json={"employee_id":"C","name":"Again"}).status_code==409
    assert client.post("/academic-years",json={"name":"Overlap","start_date":"2026-08-01","end_date":"2027-07-31"}).status_code==409
    assert client.post("/academic-years",json={"name":"Short","start_date":"2028-07-01","end_date":"2028-12-31"}).status_code==422
    outside_year=client.post("/publications",json=paper(publication_date="2000-01-01"))
    assert outside_year.status_code==201
    assert outside_year.json()["academic_year_id"] is None


def test_drilldown_preserves_dashboard_faculty_filter(setup):
    client,_,_=setup
    assert client.post("/publications",json=paper()).status_code==201
    other=paper("10.1234/b-only");other["authors"]=[author(1,"FACULTY",2,True)]
    assert client.post("/publications",json=other).status_code==201
    rows=report(client,"/publication-kpis/faculty?faculty_id=1").json()
    assert rows[1]["authored"]==1 and rows[1]["claimed"]==0
    assert len(client.get("/publications?faculty_id=1&drill_faculty_id=2&metric=total").json())==1
    assert client.get("/publications?faculty_id=1&drill_faculty_id=2&metric=claimed").json()==[]


def test_migration_and_seed_rerun_preserve_records(setup,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from backend import seed
    client,factory,_=setup
    record=client.post("/publications",json=paper()).json()
    command.upgrade(Config("alembic.ini"),"head")
    monkeypatch.setattr(seed,"SessionLocal",factory)
    seed.seed()
    seed.seed()
    assert client.get(f"/publications/{record['id']}").json()["title"]==record["title"]
    assert len(client.get("/masters").json()["academic_years"])==5


def test_database_doi_uniqueness_and_foreign_keys(setup):
    client,factory,_=setup
    first=client.post("/publications",json=paper()).json()
    second=client.post("/publications",json=paper("10.1234/p2")).json()
    with factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE publications SET doi='10.1234/P1' WHERE id=:id"),{"id":second["id"]})
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE publication_authors SET faculty_id=999 WHERE publication_id=:id AND faculty_id=1"),{"id":first["id"]})
        db.rollback()


def test_evidence_size_limit_cleans_partial_upload(setup):
    client,_,tmp=setup
    record=client.post("/publications",json=paper()).json()
    response=client.post(f"/publications/{record['id']}/evidence",files={"file":("large.pdf",b"x"*(25*1024*1024+1),"application/pdf")})
    assert response.status_code==413
    assert not list((tmp/"evidence").rglob("*.pdf"))
    assert client.get(f"/publications/{record['id']}").json()["evidence_count"]==0
