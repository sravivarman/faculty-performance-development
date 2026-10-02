import json

import pytest
from sqlalchemy import select

from backend.approve_historical_aliases import ALIASES_PATH, approve_aliases
from backend.matching import reconcile_faculty_name
from backend.models import Faculty
from backend.name_variants import normalize_person_name
from backend.seed_faculty import seed_faculty


def populated(db):
    seed_faculty(db)
    db.add_all([Faculty(employee_id="VCE1476", name="B Praveen Kumar", is_active=False, name_variants=["Existing approved alias"]),
                Faculty(employee_id="VCE967", name="Patil Mounica", is_active=False)])
    db.commit()


def test_approved_aliases_are_additive_idempotent_and_preserve_identity_status(setup):
    _, factory, _ = setup
    with factory() as db:
        populated(db)
        faculty=list(db.scalars(select(Faculty)))
        before={p.employee_id:(p.id,p.name,p.designation,p.is_active,p.orcid,p.scopus_author_id,list(p.name_variants),dict(p.name_variant_strengths)) for p in faculty}
        first=approve_aliases(db);second=approve_aliases(db)
        assert first["added_normalized_variants"]==16
        assert second["added_normalized_variants"]==0
        assert first["variant_count"]==second["variant_count"]
        approvals=json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
        faculty=list(db.scalars(select(Faculty)))
        for person in faculty:
            old=before[person.employee_id]
            assert (person.id,person.name,person.designation,person.is_active,person.orcid,person.scopus_author_id)==old[:6]
            assert set(old[6])<=set(person.name_variants)
            assert all(person.name_variant_strengths[k]==v for k,v in old[7].items())
            for alias in approvals.get(person.employee_id,[]):
                key=normalize_person_name(alias)
                assert person.name_variant_strengths[key]=="STRONG"
                owners=[p for p in faculty if key in {normalize_person_name(v) for v in [p.name,*p.name_variants]}]
                assert [p.employee_id for p in owners]==[person.employee_id]
        assert reconcile_faculty_name("Archana Chittari",faculty)["match_source"]=="UNMATCHED"
        # Subsequent base-roster seeding must retain later-approved aliases.
        seed_faculty(db)
        for person in faculty:
            for alias in approvals.get(person.employee_id,[]):
                assert normalize_person_name(alias) in {normalize_person_name(v) for v in person.name_variants}
        assert not db.scalar(select(Faculty).where(Faculty.name=="Archana Chittari"))


def test_conflict_with_inactive_canonical_name_stops_before_any_update(setup):
    _, factory, _ = setup
    with factory() as db:
        populated(db)
        db.add(Faculty(employee_id="CONFLICT",name="Hari Shankar Jain",is_active=False));db.commit()
        before={p.employee_id:list(p.name_variants) for p in db.scalars(select(Faculty))}
        with pytest.raises(ValueError,match="Alias conflicts; no records changed"):
            approve_aliases(db)
        assert before=={p.employee_id:list(p.name_variants) for p in db.scalars(select(Faculty))}


def test_missing_historical_faculty_is_not_created(setup):
    _, factory, _ = setup
    with factory() as db:
        seed_faculty(db)
        with pytest.raises(ValueError,match="Missing Faculty Master IDs"):
            approve_aliases(db)
        assert db.scalar(select(Faculty).where(Faculty.employee_id=="VCE1476")) is None
