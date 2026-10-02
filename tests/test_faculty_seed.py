import json

import pytest
from sqlalchemy import select, func

from backend.matching import match_author, reconcile_faculty_name
from backend.models import Faculty, Publication
from backend.name_variants import normalize_person_name
from backend.reconcile_claimants import reconcile, write_report
from backend.seed_faculty import ROSTER_PATH, seed_faculty


@pytest.mark.parametrize("value,expected", [
    (" Dr.  H. S. Jain ", "hs jain"), ("H.S. Jain", "hs jain"), ("HS Jain", "hs jain"),
    (" Mr.. B.  Mohan ", "b mohan"), ("Ms. G. Swetha", "g swetha"),
    ("Ravivarman, S.", "ravivarman s"), ("Dr. T. Anuradha Devi", "t anuradha devi"),
])
def test_person_normalization(value, expected):
    assert normalize_person_name(value) == expected


def test_seed_idempotent_preserves_existing_identifiers_and_activities(setup):
    _, factory, _ = setup
    with factory() as db:
        person = Faculty(employee_id="VCE085", name="Old name", is_active=False, orcid="0000-0002-2222-2222", scopus_author_id="real-id")
        db.add(person);db.commit();identity=person.id
        before=db.scalar(select(func.count()).select_from(Publication))
        first=seed_faculty(db);second=seed_faculty(db)
        assert first["added"] == 16 and second["added"] == 0
        assert first["faculty_master_count"] == second["faculty_master_count"] == 19
        assert first["faculty_name_variant_count"] == second["faculty_name_variant_count"]
        person=db.get(Faculty,identity)
        assert person.name == "Dr. Md. Asif" and person.is_active
        assert person.orcid == "0000-0002-2222-2222" and person.scopus_author_id == "real-id"
        assert db.scalar(select(func.count()).select_from(Publication)) == before
        roster=json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
        faculty=list(db.scalars(select(Faculty)))
        for entry in roster:
            person=next(p for p in faculty if p.employee_id==entry["employee_id"])
            assert person.name == entry["name"] and person.designation == entry["designation"]
            assert person.is_active
            keys=[normalize_person_name(v) for v in person.name_variants]
            assert len(keys)==len(set(keys))
            assert set(keys)=={normalize_person_name(v) for v in entry["name_variants"]}
            assert set(person.name_variant_strengths)==set(keys)
            for weak in entry["weak_variants"]:
                assert person.name_variant_strengths[normalize_person_name(weak)]=="WEAK"


@pytest.mark.parametrize("value,employee,source", [
    ("Md Asif", "VCE085", "CANONICAL"), ("M. Asif", "VCE085", "WEAK_VARIANT"),
    ("M Perumal", "VCE1496", "WEAK_VARIANT"), ("F Unnisa", "VCE1199", "WEAK_VARIANT"),
    ("Shanmugasundaram Ravivarman", "VCE1127", "STRONG_VARIANT"),
    ("A Ramakrishna", "VCE306", "STRONG_VARIANT"), ("A Anandakumar", "VCE1009", "STRONG_VARIANT"),
    ("G Indira Rani", "VCE1430", "STRONG_VARIANT"), ("B Bala Krishna", "VCE1837", "STRONG_VARIANT"),
    ("Dr. H S Jain", "VCE640", "CANONICAL"), ("G Swetha", "VCE1546", "CANONICAL"),
])
def test_approved_match_priority_and_weak_review(setup,value,employee,source):
    _,factory,_=setup
    with factory() as db:
        seed_faculty(db);faculty=list(db.scalars(select(Faculty)))
        match=reconcile_faculty_name(value,faculty)
        assert match["employee_id"]==employee and match["match_source"]==source
        author=match_author({"author_name_from_source":value},faculty,[])
        if source=="WEAK_VARIANT":
            assert match["requires_review"]
            assert author["matching_status"]=="SUGGESTED" and author.get("faculty_id") is None
        else:
            assert not match["requires_review"]
            assert author["matching_status"]=="EXACT"


def test_collisions_and_spelling_alternatives_require_review(setup):
    _,factory,_=setup
    with factory() as db:
        seed_faculty(db)
        db.add(Faculty(employee_id="OTHER",name="M. Asif",name_variants=[]));db.commit()
        faculty=list(db.scalars(select(Faculty)))
        assert reconcile_faculty_name("M Asif",faculty)["match_source"]=="AMBIGUOUS"
        assert match_author({"author_name_from_source":"M Asif"},faculty,[]).get("faculty_id") is None
        assert reconcile_faculty_name("G Shwetha",faculty)["match_source"]=="UNMATCHED"
        assert reconcile_faculty_name("Himanshu Jain",faculty)["match_source"]=="UNMATCHED"


def test_orcid_overrides_name_variants_and_conflicts(setup):
    _,factory,_=setup
    with factory() as db:
        seed_faculty(db)
        person=db.scalar(select(Faculty).where(Faculty.employee_id=="VCE085"))
        person.orcid="0000-0002-2222-2222";db.commit()
        faculty=list(db.scalars(select(Faculty)))
        match=reconcile_faculty_name("Unrelated source name",faculty,person.orcid)
        assert match["employee_id"]=="VCE085" and match["match_source"]=="ORCID"
        assert match_author({"author_name_from_source":"M. Asif","orcid_from_source":person.orcid},faculty,[])["faculty_id"]==person.id
        assert reconcile_faculty_name("Md Asif",[person],"0000-0003-3333-3333")["match_source"]=="UNMATCHED"


def test_reconciliation_preserves_blank_unmatched_ambiguous_and_all_rows(setup,tmp_path):
    _,factory,_=setup
    with factory() as db:
        seed_faculty(db)
        faculty=list(db.scalars(select(Faculty)))
        source={"source":"test.xlsx","sheet":"Journal","rows":[
            {"excel_row":i+2,"author_value":value,"has_title":True}
            for i,value in enumerate(["Md Asif","Md Asif","M. Asif","Unknown Claimant","", "G Indira Rani"])]}
        result=reconcile(source,faculty)
        assert result["summary"]["total_journal_rows"]==result["summary"]["grouped_row_total"]==6
        assert result["summary"]["blank_claimant_rows"]==1
        assert result["summary"]["canonical_matches"]==1
        assert result["summary"]["weak_variant_matches"]==1
        assert result["summary"]["unmatched_values"]==2
        assert result["summary"]["strong_variant_matches"]==1
        assert sorted(n for r in result["claimants"] for n in r["source_rows"])==list(range(2,8))
        write_report(result,tmp_path)
        assert (tmp_path/"claimant-reconciliation.csv").is_file()
        assert "6 grouped rows = 6" in (tmp_path/"claimant-reconciliation.md").read_text(encoding="utf-8")


def test_master_api_deduplicates_variants_and_preserves_weak_safeguards(setup):
    client,_,_=setup
    payload={"employee_id":"NEW","name":"Dr. Md. Asif","name_variants":["Md Asif","Md. Asif","M Asif","M. Asif"],"name_variant_strengths":{"M. Asif":"WEAK"}}
    response=client.post("/faculty",json=payload)
    assert response.status_code==201,response.text
    person=response.json()
    assert person["name_variants"]==["Md Asif","M Asif"]
    assert person["weak_name_variants"]==["M Asif"]
    payload.pop("name_variant_strengths")
    assert client.put(f'/faculty/{person["id"]}',json=payload).json()["weak_name_variants"]==["M Asif"]
    payload["name_variant_strengths"]={"Unapproved alias":"WEAK"}
    assert client.put(f'/faculty/{person["id"]}',json=payload).status_code==422


def test_health_reports_actual_connection_database_path(setup):
    client, _, root = setup
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    from pathlib import Path
    assert Path(response.json()["database_path"]).resolve() == (root / "test.db").resolve()
