from backend.models import BookContributor, PatentInventor, PublicationAuthor
from conftest import paper


def patent_payload():
    return {
        "title": "Delete-safe patent", "application_number": "DELETE-PATENT", "patent_office": "Indian Patent Office", "country": "India",
        "patent_type": "UTILITY", "current_status": "FILED", "filing_date": "2026-08-10",
        "inventors": [
            {"inventor_order": 1, "inventor_name": "Faculty 1", "person_type": "FACULTY", "institution_scope": "CURRENT_DEPARTMENT", "faculty_id": 1, "student_id": None, "is_claiming_faculty": True},
            {"inventor_order": 2, "inventor_name": "Student 1", "person_type": "STUDENT", "institution_scope": "CURRENT_DEPARTMENT", "faculty_id": None, "student_id": 1, "is_claiming_faculty": False},
        ],
    }


def book_payload():
    return {
        "work_type": "BOOK", "title": "Delete-safe book", "publisher": "Example Press", "publication_date": "2026-08-15", "doi": "10.1234/delete-safe-book",
        "contributors": [
            {"contributor_order": 1, "contributor_name": "Faculty 1", "role": "AUTHOR", "person_type": "FACULTY", "institution_scope": "CURRENT_DEPARTMENT", "faculty_id": 1, "student_id": None, "is_claiming_faculty": True},
            {"contributor_order": 2, "contributor_name": "Student 1", "role": "AUTHOR", "person_type": "STUDENT", "institution_scope": "CURRENT_DEPARTMENT", "faculty_id": None, "student_id": 1, "is_claiming_faculty": False},
        ],
    }


def test_permanent_deletion_removes_only_owned_relations_and_preserves_masters(setup):
    client, factory, _ = setup
    publication = client.post("/publications", json=paper("10.1234/delete-safe-publication"))
    patent = client.post("/patents", json=patent_payload())
    book = client.post("/books", json=book_payload())
    assert publication.status_code == patent.status_code == book.status_code == 201

    for path, response in (("/publications", publication), ("/patents", patent), ("/books", book)):
        deleted = client.delete(f"{path}/{response.json()['id']}/permanent")
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] == response.json()["id"]
        assert client.delete(f"{path}/{response.json()['id']}/permanent").status_code == 404

    with factory() as db:
        assert db.query(PublicationAuthor).count() == 0
        assert db.query(PatentInventor).count() == 0
        assert db.query(BookContributor).count() == 0
    masters = client.get("/masters").json()
    assert [person["id"] for person in masters["faculty"]] == [1, 2]
    assert [person["id"] for person in masters["students"]] == [1, 2]


def test_soft_deactivate_and_reactivate_remain_separate_from_permanent_delete(setup):
    client, _, _ = setup
    publication = client.post("/publications", json=paper("10.1234/delete-lifecycle"))
    assert publication.status_code == 201
    identity = publication.json()["id"]
    assert client.delete(f"/publications/{identity}").json()["is_active"] is False
    assert client.get(f"/publications/{identity}").status_code == 200
    restored = client.post(f"/publications/{identity}/reactivate")
    assert restored.status_code == 200 and restored.json()["is_active"] is True
