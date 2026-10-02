from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend import db as database
from backend.db import get_db, make_engine
from backend.main import app
from backend.models import AcademicYear, Faculty, Student


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "EVIDENCE_ROOT", tmp_path / "evidence")
    command.upgrade(Config("alembic.ini"), "head")
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            AcademicYear(id=1, name="2026-27", start_date=date(2026, 7, 1), end_date=date(2027, 6, 30)),
            AcademicYear(id=2, name="2027-28", start_date=date(2027, 7, 1), end_date=date(2028, 6, 30)),
            Faculty(id=1, employee_id="A", name="Faculty A", orcid="0000-0001-2345-6789", name_variants=["A. Faculty"]),
            Faculty(id=2, employee_id="B", name="Faculty B", name_variants=["B. Faculty"]),
            Student(id=1, roll_number="X", name="Student X", name_variants=["X. Student"]),
            Student(id=2, roll_number="Y", name="Student Y"),
        ])
        db.commit()
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, factory, tmp_path
    app.dependency_overrides.clear()
    engine.dispose()


def author(order, kind, identity=None, claimant=False):
    return {"author_order": order, "author_name_from_source": f"{kind} {identity or 'Y'}", "person_type": kind,
            "faculty_id": identity if kind == "FACULTY" else None,
            "student_id": identity if kind == "STUDENT" else None,
            "is_claiming_faculty": claimant, "is_first_author": order == 1}


def paper(doi="10.1234/p1", publication_date="2026-09-18"):
    return {"doi": doi, "title": "Paper " + str(doi), "publication_date": publication_date,
            "publication_type": "JOURNAL", "journal_conference_name": "Research Journal",
            "indexing": ["SCOPUS", "SCI", "SCIE"],
            "authors": [author(1,"FACULTY",1,True),author(2,"FACULTY",2),author(3,"STUDENT",1),author(4,"EXTERNAL")]}


def report(client, path, from_date="1900-01-01", to_date="2100-12-31"):
    """Explicit broad date range for tests concerned with non-date behavior."""
    from urllib.parse import parse_qsl, urlencode, urlsplit
    parsed = urlsplit(path)
    params = dict(parse_qsl(parsed.query))
    params.setdefault("from_date",from_date)
    params.setdefault("to_date",to_date)
    return client.get(parsed.path+"?"+urlencode(params))
