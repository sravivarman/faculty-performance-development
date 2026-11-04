from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend import db as database
from backend.db import make_engine


def test_department_master_lifecycle_and_reference_protection(setup):
    client, _, _ = setup
    initial = client.get("/departments")
    assert initial.status_code == 200
    assert [row["code"] for row in initial.json()].count("EEE") == 1

    ece = client.post("/departments", json={"code": "ece", "name": "Electronics and Communication Engineering"})
    assert ece.status_code == 201, ece.text
    ece_id = ece.json()["id"]
    assert ece.json()["code"] == "ECE"
    assert client.post("/departments", json={"code": "ECE", "name": "Duplicate"}).status_code == 409

    edited = client.put(f"/departments/{ece_id}", json={"code": "ECE", "name": "Electronics & Communication Engineering"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "Electronics & Communication Engineering"

    inactive = client.post(f"/departments/{ece_id}/deactivate")
    assert inactive.status_code == 200
    assert all(row["id"] != ece_id for row in client.get("/departments/active").json())
    assert client.post(f"/departments/{ece_id}/reactivate").status_code == 200

    faculty = client.post("/faculty", json={
        "employee_id": "DEPT-F-1", "name": "Department Faculty",
        "department_id": ece_id, "department_effective_from": "2026-07-01",
        "name_variants": ["Dept Faculty Alias"],
    })
    assert faculty.status_code == 201, faculty.text
    faculty_id = faculty.json()["id"]
    assert faculty.json()["department"]["code"] == "ECE"
    assert faculty.json()["department_history"][0]["effective_from"] == "2026-07-01"
    assert client.delete(f"/departments/{ece_id}").status_code == 409

    cse = client.post("/departments", json={"code": "CSE", "name": "Computer Science and Engineering"})
    assert cse.status_code == 201
    transferred = client.post(f"/faculty/{faculty_id}/department-transfer", json={
        "department_id": cse.json()["id"], "effective_from": "2027-07-01",
    })
    assert transferred.status_code == 200, transferred.text
    history = transferred.json()["department_history"]
    assert transferred.json()["department"]["code"] == "CSE"
    assert {(item["department"]["code"], item["effective_to"]) for item in history} >= {("ECE", "2027-06-30"), ("CSE", None)}
    assert client.post(f"/faculty/{faculty_id}/department-transfer", json={
        "department_id": ece_id, "effective_from": "2027-01-01",
    }).status_code in {409, 422}

    student = client.post("/students", json={
        "roll_number": "DEPT-S-1", "name": "Department Student", "department_id": cse.json()["id"],
    })
    assert student.status_code == 201, student.text
    assert student.json()["department"]["code"] == "CSE"
    assert client.delete(f"/departments/{cse.json()['id']}").status_code == 409

    assert client.post(f"/departments/{ece_id}/deactivate").status_code == 200
    rejected = client.post("/faculty", json={"employee_id": "DEPT-F-2", "name": "Inactive Department Faculty", "department_id": ece_id})
    assert rejected.status_code == 422


def test_unused_faculty_deletes_owned_affiliations_and_student_department_can_change(setup):
    client, _, _ = setup
    department = client.post("/departments", json={"code": "ME", "name": "Mechanical Engineering"}).json()
    faculty = client.post("/faculty", json={"employee_id": "DEPT-F-DELETE", "name": "Delete Department Faculty", "department_id": department["id"]})
    assert faculty.status_code == 201, faculty.text
    identity = faculty.json()["id"]
    assert client.delete(f"/faculty/{identity}").status_code == 200
    # The exclusively-owned history no longer blocks the unused Department.
    assert client.delete(f"/departments/{department['id']}").status_code == 200

    cse = client.post("/departments", json={"code": "CSE2", "name": "Computer Science"}).json()
    eee = next(row for row in client.get("/departments").json() if row["code"] == "EEE")
    student = client.post("/students", json={"roll_number": "DEPT-S-CHANGE", "name": "Change Student", "department_id": eee["id"]})
    assert student.status_code == 201
    updated = client.put(f"/students/{student.json()['id']}", json={
        "roll_number": "DEPT-S-CHANGE", "name": "Change Student", "department_id": cse["id"], "is_active": False,
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["department"]["code"] == "CSE2"
    assert updated.json()["is_active"] is False


def test_department_migration_backfills_preexisting_people_without_fabricating_dates(tmp_path, monkeypatch):
    """Upgrade a pre-Phase-1 schema, not the live database, through the new head."""
    engine = make_engine(f"sqlite:///{tmp_path / 'legacy.db'}", poolclass=NullPool)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "c8a1d5e4f9b0")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO faculty (id, employee_id, name, designation, orcid, scopus_author_id, name_variants, name_variant_strengths, is_active, created_at, updated_at) "
                "VALUES (91, 'LEGACY-F', 'Legacy Faculty', NULL, NULL, NULL, '[]', '{}', 1, :now, :now)"
            ), {"now": date(2026, 1, 1)})
            connection.execute(text(
                "INSERT INTO students (id, roll_number, name, batch, program, year_of_study, name_variants, is_active, created_at, updated_at) "
                "VALUES (92, 'LEGACY-S', 'Legacy Student', NULL, NULL, NULL, '[]', 1, :now, :now)"
            ), {"now": date(2026, 1, 1)})
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM departments WHERE code = 'EEE'")).scalar_one() == 1
            affiliation = connection.execute(text(
                "SELECT effective_from, effective_to, source FROM faculty_department_affiliations WHERE faculty_id = 91"
            )).one()
            assert affiliation == (None, None, "MIGRATION_BASELINE")
            assert connection.execute(text(
                "SELECT d.code FROM students s JOIN departments d ON d.id = s.department_id WHERE s.id = 92"
            )).scalar_one() == "EEE"
            assert connection.execute(text("SELECT employee_id FROM faculty WHERE id = 91")).scalar_one() == "LEGACY-F"
            assert connection.execute(text("SELECT roll_number FROM students WHERE id = 92")).scalar_one() == "LEGACY-S"
    finally:
        engine.dispose()
