"""Phase 2 institution-wide contributor and attribution regression coverage."""

from datetime import date

from backend.department_attribution import resolve_faculty_departments
from backend.models import FacultyDepartmentAffiliation


def create_department(client, code, name):
    response = client.post("/departments", json={"code": code, "name": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_faculty(client, employee_id, name, department_id, effective_from="2025-07-01"):
    response = client.post("/faculty", json={
        "employee_id": employee_id,
        "name": name,
        "department_id": department_id,
        "department_effective_from": effective_from,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_department_master_links_preserve_one_record_and_claimant(setup):
    client, _, _ = setup
    eee = next(item for item in client.get("/departments").json() if item["code"] == "EEE")
    cse = create_department(client, "CSE", "Computer Science and Engineering")
    eee_faculty = create_faculty(client, "PH2-EEE", "Faculty EEE", eee["id"])
    cse_faculty = create_faculty(client, "PH2-CSE", "Faculty CSE", cse["id"])

    publication = client.post("/publications", json={
        "doi": "10.1234/phase2-cross-department",
        "title": "Cross Department Publication",
        "publication_type": "JOURNAL",
        "journal_conference_name": "Institutional Research",
        "publication_date": "2026-09-01",
        "authors": [
            {"author_order": 1, "author_name_from_source": "Faculty EEE", "person_type": "FACULTY", "faculty_id": eee_faculty["id"], "is_claiming_faculty": True},
            {"author_order": 2, "author_name_from_source": "Faculty CSE", "person_type": "FACULTY", "faculty_id": cse_faculty["id"]},
            {"author_order": 3, "author_name_from_source": "External Author", "person_type": "EXTERNAL"},
        ],
    })
    assert publication.status_code == 201, publication.text
    assert [author["faculty_id"] for author in publication.json()["authors"]] == [eee_faculty["id"], cse_faculty["id"], None]
    assert [author["author_order"] for author in publication.json()["authors"]] == [1, 2, 3]

    patent = client.post("/patents", json={
        "title": "Cross Department Patent",
        "application_number": "PH2-CROSS",
        "patent_office": "Indian Patent Office",
        "patent_type": "UTILITY",
        "filing_date": "2026-09-01",
        "current_status": "FILED",
        "inventors": [
            {"inventor_order": 1, "inventor_name": "Faculty EEE", "person_type": "FACULTY", "institution_scope": "CURRENT_DEPARTMENT", "faculty_id": eee_faculty["id"], "is_claiming_faculty": True},
            {"inventor_order": 2, "inventor_name": "Faculty CSE", "person_type": "FACULTY", "institution_scope": "SAME_INSTITUTION_OTHER_DEPARTMENT", "faculty_id": cse_faculty["id"], "department_name": "CSE"},
        ],
    })
    assert patent.status_code == 201, patent.text
    assert [inventor["faculty_id"] for inventor in patent.json()["inventors"]] == [eee_faculty["id"], cse_faculty["id"]]

    book = client.post("/books", json={
        "work_type": "BOOK",
        "title": "Cross Department Book",
        "publisher": "VCE Press",
        "publication_date": "2026-09-01",
        "contributors": [
            {"contributor_order": 1, "contributor_name": "Faculty EEE", "role": "AUTHOR", "person_type": "FACULTY", "institution_scope": "CURRENT_DEPARTMENT", "faculty_id": eee_faculty["id"], "is_claiming_faculty": True},
            {"contributor_order": 2, "contributor_name": "Faculty CSE", "role": "AUTHOR", "person_type": "FACULTY", "institution_scope": "SAME_INSTITUTION_OTHER_DEPARTMENT", "faculty_id": cse_faculty["id"], "department_name": "CSE"},
        ],
    })
    assert book.status_code == 201, book.text
    assert [contributor["faculty_id"] for contributor in book.json()["contributors"]] == [eee_faculty["id"], cse_faculty["id"]]


def test_department_attribution_is_dated_and_never_fabricates_baseline_history(setup):
    client, factory, _ = setup
    eee = next(item for item in client.get("/departments").json() if item["code"] == "EEE")
    cse = create_department(client, "CSE", "Computer Science and Engineering")
    faculty = create_faculty(client, "PH2-ATTR", "Attribution Faculty", eee["id"], "2025-07-01")
    transferred = client.post(f"/faculty/{faculty['id']}/department-transfer", json={"department_id": cse["id"], "effective_from": "2027-07-01"})
    assert transferred.status_code == 200, transferred.text
    with factory() as db:
        db.add(FacultyDepartmentAffiliation(
            faculty_id=1,
            department_id=eee["id"],
            effective_from=None,
            effective_to=None,
            is_primary=True,
            source="MIGRATION_BASELINE",
        ))
        db.commit()
        before_transfer = resolve_faculty_departments(db, faculty["id"], activity_date=date(2026, 9, 1))
        after_transfer = resolve_faculty_departments(db, faculty["id"], activity_date=date(2027, 9, 1))
        current = resolve_faculty_departments(db, faculty["id"], mode="CURRENT")
        no_date = resolve_faculty_departments(db, faculty["id"], activity_date=None)
        legacy = resolve_faculty_departments(db, 1, activity_date=date(2020, 1, 1))
    assert before_transfer["department_codes"] == ["EEE"]
    assert after_transfer["department_codes"] == ["CSE"]
    assert current["department_codes"] == ["CSE"]
    assert no_date["resolution_status"] == "ACTIVITY_DATE_UNKNOWN"
    assert legacy["resolution_status"] == "HISTORICAL_AFFILIATION_UNVERIFIED"
