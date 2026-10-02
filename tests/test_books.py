import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.book_schemas import normalize_isbn
from backend.models import BookContributor
from conftest import report


def contributor(order, kind="FACULTY", identity=None, scope="CURRENT_DEPARTMENT", claimant=False, role="AUTHOR"):
    return {"contributor_order": order, "contributor_name": f"{kind} {identity or order}", "role": role,
            "person_type": kind, "institution_scope": scope, "is_claiming_faculty": claimant,
            "faculty_id": identity if kind == "FACULTY" and scope == "CURRENT_DEPARTMENT" else None,
            "student_id": identity if kind == "STUDENT" and scope == "CURRENT_DEPARTMENT" else None,
            "department_name": "CSE" if scope == "SAME_INSTITUTION_OTHER_DEPARTMENT" else None,
            "institution_name": "External University" if scope == "EXTERNAL_INSTITUTION" else None}


def book(kind="BOOK_CHAPTER", doi="10.1234/b1", day="2026-08-15"):
    return {"work_type": kind, "title": "Power systems", "parent_book_title": "Engineering Handbook" if kind == "BOOK_CHAPTER" else None,
            "page_range": "15–28" if kind == "BOOK_CHAPTER" else None, "isbn": "978-0-306-40615-7", "publisher": "Example Press",
            "publication_date": day, "doi": doi, "contributors": [contributor(1, identity=1, claimant=True),
            contributor(2, identity=2), contributor(3, scope="SAME_INSTITUTION_OTHER_DEPARTMENT"),
            contributor(4, "STUDENT", 1), contributor(5, "EXTERNAL_PERSON", scope="EXTERNAL_INSTITUTION")]}


def create(client, payload=None):
    response = client.post("/books", json=payload or book())
    assert response.status_code == 201, response.text
    return response.json()


def test_requested_counting_example_and_all_drilldowns(setup):
    client, _, _ = setup
    record = create(client)
    counts = report(client, "/book-kpis", "2026-07-01", "2026-09-30").json()
    assert counts == {"total": 1, "books": 0, "chapters": 1, "with_students": 1, "interdepartmental": 1,
                      "external_collaboration": 1, "unique_faculty": 2, "unique_students": 1}
    faculty = report(client, "/book-kpis/faculty").json()
    assert [(f["claimed"], f["authored"], f["chapters_claimed"], f["chapters_authored"]) for f in faculty] == [(1, 1, 1, 1), (0, 1, 0, 1)]
    student = report(client, "/book-kpis/students").json()[0]
    assert student["total_works"] == student["chapters_authored"] == 1
    assert [p["id"] for p in student["faculty_collaborators"]] == [1, 2]
    for metric in counts:
        rows = report(client, f"/books?metric={metric}", "2026-07-01", "2026-09-30").json()
        assert [p["id"] for p in rows] == ([] if metric == "books" else [record["id"]])
    for kind, rows in (("faculty", faculty), ("student", report(client, "/book-kpis/students").json())):
        for row in rows:
            for metric in ("books_claimed", "books_authored", "chapters_claimed", "chapters_authored", "claimed", "authored"):
                if metric in row:
                    drill = report(client, f'/books?metric={metric}&drill_{kind}_id={row["id"]}').json()
                    assert len(drill) == row[metric]
    assert record["contributors"][2]["faculty_id"] is None
    assert record["contributors"][2]["institution_name"] == "Vardhaman College of Engineering"
    assert record["current_department_faculty_count"] == 2
    assert report(client, "/dashboard-kpis").json()["books_total"] == 1
    assert report(client, "/faculty-kpis").json()[1]["books_authored"] == 1


def test_book_creation_editor_and_author_roles(setup):
    client, _, _ = setup
    data = book("BOOK")
    data.update(edition="Second", chapter_number="unnecessary", page_range="unnecessary")
    data["contributors"][0]["role"] = "EDITOR"
    record = create(client, data)
    assert record["edition"] == "Second"
    assert record["parent_book_title"] is record["chapter_number"] is record["page_range"] is None
    faculty = report(client, "/book-kpis/faculty").json()
    assert faculty[0]["books_claimed"] == 1 and faculty[0]["books_authored"] == 0
    assert faculty[1]["books_authored"] == 1


@pytest.mark.parametrize("value", ["978-0-306-40615-7", "9780306406157", "0-306-40615-2"])
def test_isbn_normalization(value):
    assert normalize_isbn(value) == "9780306406157"


@pytest.mark.parametrize("value", ["123", "9780306406158", "0306406153", "978-abc"])
def test_invalid_isbn(value):
    with pytest.raises(ValueError):
        normalize_isbn(value)


def test_doi_normalization_and_hard_duplicate_block(setup):
    client, _, _ = setup
    record = create(client, book(doi=" HTTPS://doi.org/10.1234/B1 "))
    assert record["doi"] == "10.1234/b1"
    for kind in ("BOOK", "BOOK_CHAPTER"):
        duplicate = book(kind, doi="doi:10.1234/b1")
        duplicate["duplicate_acknowledged"] = True
        response = client.post("/books", json=duplicate)
        assert response.status_code == 409
        assert response.json()["detail"]["book_id"] == record["id"]


@pytest.mark.parametrize("kind", ["BOOK", "BOOK_CHAPTER"])
def test_possible_duplicates_are_reviewed_not_merged(setup, kind):
    client, _, _ = setup
    record = create(client, book(kind, doi=None))
    data = book(kind, doi=None)
    data["title"] = " POWER   SYSTEMS "
    data["isbn"] = "0-306-40615-2"
    response = client.post("/books", json=data)
    assert response.status_code == 409
    assert response.json()["detail"]["possible_duplicate_ids"] == [record["id"]]
    data["duplicate_acknowledged"] = True
    assert create(client, data)["id"] != record["id"]


def test_no_isbn_manual_entry_and_duplicate_warning(setup):
    client, _, _ = setup
    data = book(doi=None);data["isbn"] = None
    create(client, data)
    assert client.post("/books", json=data).status_code == 409
    data["title"] = "Another work"
    assert create(client, data)["isbn"] is None


@pytest.mark.parametrize("change", ["two_claimants", "external_claimant", "editor_claimant", "unknown_master", "duplicate_author", "wrong_mapping", "missing_parent", "missing_page", "missing_authors"])
def test_invalid_creation_is_rejected(setup, change):
    client, _, _ = setup
    data = book()
    if change == "two_claimants": data["contributors"][1]["is_claiming_faculty"] = True
    if change == "external_claimant": data["contributors"][4]["is_claiming_faculty"] = True
    if change == "editor_claimant": data["contributors"][0]["role"] = "EDITOR"
    if change == "unknown_master": data["contributors"][0]["faculty_id"] = 999
    if change == "duplicate_author": data["contributors"].append({**data["contributors"][1], "contributor_order": 6})
    if change == "wrong_mapping": data["contributors"][2]["faculty_id"] = 2
    if change == "missing_parent": data["parent_book_title"] = ""
    if change == "missing_page": data["page_range"] = None
    if change == "missing_authors":
        for c in data["contributors"]: c.update(role="EDITOR", is_claiming_faculty=False)
    assert client.post("/books", json=data).status_code == 422
    assert client.get("/books?department_only=false").json() == []


def test_historical_unclaimed_and_editor_only_chapter_exclusion(setup):
    client, factory, _ = setup
    data = book();data["contributors"][0]["is_claiming_faculty"] = False
    for c in data["contributors"]:
        if c["institution_scope"] == "CURRENT_DEPARTMENT": c["role"] = "EDITOR"
    assert client.post('/books', json=data).status_code == 422
    # A historical unclaimed record remains readable/editable after upgrade.
    from backend.book_schemas import BookInput
    from backend.models import BookPublication, BookContributor
    from backend.book_services import book_dict
    parsed = BookInput(**data)
    with factory() as db:
        work = BookPublication(**parsed.model_dump(exclude={'contributors', 'duplicate_acknowledged'}))
        work.contributors = [BookContributor(**c.model_dump()) for c in parsed.contributors]
        db.add(work); db.commit()
        record = book_dict(work, db)
    assert record["evidence_count"] == 0
    assert report(client, "/book-kpis").json()["total"] == 0
    assert client.get("/books").json() == []
    assert len(client.get("/books?department_only=false").json()) == 1
    data["contributors"][1]["role"] = "AUTHOR"
    assert client.put(f'/books/{record["id"]}', json=data).status_code == 200
    counts = report(client, "/book-kpis").json()
    assert counts["total"] == 1 and counts["unique_faculty"] == 1 and counts["with_students"] == 0


def test_person_both_author_and_editor_is_counted_once(setup):
    client, _, _ = setup
    data = book("BOOK")
    data["contributors"].extend([{**data["contributors"][0], "contributor_order": 6, "role": "EDITOR", "is_claiming_faculty": False},
                                 {**data["contributors"][3], "contributor_order": 7, "role": "EDITOR"}])
    record = create(client, data)
    assert len(record["contributors"]) == 7
    assert record["current_department_student_count"] == 1
    assert report(client, "/book-kpis").json()["total"] == 1
    assert report(client, "/book-kpis/students").json()[0]["authored"] == 1


def test_from_and_to_boundaries_and_outside_dates(setup):
    client, _, _ = setup
    for index, day in enumerate(["2026-06-30", "2026-07-01", "2026-09-30", "2026-10-01"]):
        create(client, book(doi=f"10.1234/date{index}", day=day))
    assert report(client, "/book-kpis", "2026-07-01", "2026-09-30").json()["total"] == 2
    rows = report(client, "/books", "2026-07-01", "2026-09-30").json()
    assert {r["publication_date"] for r in rows} == {"2026-07-01", "2026-09-30"}
    assert report(client, "/book-kpis", "2026-07-01", "2026-07-01").json()["total"] == 1
    for query in ("", "?from_date=2026-07-01", "?from_date=2026-09-30&to_date=2026-07-01"):
        assert client.get("/book-kpis"+query).status_code == 422
    assert client.get("/books?to_date=2026-09-30").status_code == 422
    assert report(client, "/books?metric=invalid").status_code == 422


@pytest.mark.parametrize("query, expected", [("work_type=BOOK", 0), ("work_type=BOOK_CHAPTER", 1), ("faculty_id=2", 1),
    ("student_participation=true", 1), ("student_participation=false", 0), ("interdepartmental=true", 1),
    ("interdepartmental=false", 0), ("external_collaboration=true", 1), ("external_collaboration=false", 0),
    ("publisher=Example%20Press", 1), ("publisher=Missing", 0), ("isbn_search=978030640", 1), ("isbn_search=0306406152", 1)])
def test_filters_match_department_and_drilldowns(setup, query, expected):
    client, _, _ = setup
    create(client)
    assert report(client, "/book-kpis?"+query).json()["total"] == expected
    assert len(report(client, "/books?"+query).json()) == expected


def test_update_claimant_roles_deactivate_and_audit(setup):
    client, _, _ = setup
    record = create(client);data = book()
    data["contributors"][0]["is_claiming_faculty"] = False
    data["contributors"][1]["is_claiming_faculty"] = True
    response = client.put(f'/books/{record["id"]}', json=data)
    assert response.status_code == 200
    assert report(client, "/book-kpis/faculty").json()[1]["claimed"] == 1
    detail = client.get(f'/books/{record["id"]}').json()
    assert [c["action"] for c in detail["change_log"]] == ["UPDATE", "CREATE"]
    assert client.delete(f'/books/{record["id"]}').status_code == 200
    assert report(client, "/book-kpis").json()["total"] == 0
    assert report(client, "/book-kpis?include_inactive=true").json()["total"] == 1


@pytest.mark.parametrize("kind", ["BOOK", "BOOK_CHAPTER"])
def test_multiple_evidence_storage_view_download_remove_and_owner_isolation(setup, kind):
    client, _, root = setup
    record = create(client, book(kind));second = create(client, book(kind, doi="10.1234/b2"))
    ids = []
    for name, category in (("cover.pdf", "COVER_PAGE"), ("chapter.pdf", "FULL_CHAPTER")):
        response = client.post(f'/books/{record["id"]}/evidence', files={"file": (name, b"%PDF-1.4 evidence", "application/pdf")}, data={"evidence_type": category})
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
        assert "storage_path" not in response.json()
    files = list((root/"evidence"/"2026-27"/kind/str(record["id"])).glob("*.pdf"))
    assert len(files) == 2
    assert client.get(f'/books/{record["id"]}').json()["evidence_count"] == 2
    assert client.get(f'/books/{second["id"]}/evidence/{ids[0]}').status_code == 404
    assert client.get(f'/patents/{record["id"]}/evidence/{ids[0]}').status_code == 404
    view = client.get(f'/books/{record["id"]}/evidence/{ids[0]}')
    assert view.content == b"%PDF-1.4 evidence"
    assert view.headers["content-disposition"].startswith("inline")
    assert client.get(f'/books/{record["id"]}/evidence/{ids[0]}?download=true').headers["content-disposition"].startswith("attachment")
    assert client.delete(f'/books/{record["id"]}/evidence/{ids[0]}').status_code == 200
    assert client.get(f'/books/{record["id"]}').json()["evidence_count"] == 1
    assert len(list(files[0].parent.glob("*.pdf"))) == 1


def test_claimant_and_evidence_ownership_database_constraints(setup):
    client, factory, _ = setup
    record = create(client)
    with factory() as db:
        second = db.scalar(select(BookContributor).where(BookContributor.book_record_id == record["id"], BookContributor.faculty_id == 2))
        second.is_claiming_faculty = True
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("INSERT INTO evidence_files (book_record_id,publication_id,original_filename,storage_path,content_type,size_bytes,sha256,evidence_type,created_at,updated_at) VALUES (:id,999,'a','a','application/pdf',1,'a','OTHER',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id": record["id"]})
        db.rollback()


def test_optional_metadata_is_preview_only_and_failure_keeps_manual_entry(setup, monkeypatch):
    from backend import book_api
    from backend.metadata import MetadataError
    client, _, _ = setup
    monkeypatch.setattr(book_api.provider, "fetch_by_doi", lambda doi: {"doi": doi, "title": "Fetched chapter", "publisher": "Press",
        "authors": [{"author_name_from_source": "Person A"}], "raw_metadata_json": {"message": {"ISBN": ["9780306406157"]}}})
    response = client.get("/book-metadata?doi=https://doi.org/10.1234/BOOK")
    assert response.status_code == 200
    assert response.json()["doi"] == "10.1234/book"
    assert response.json()["contributors"][0]["institution_scope"] == "UNKNOWN"
    assert client.get("/books?department_only=false").json() == []
    def fail(doi): raise MetadataError("Provider unavailable. Continue manually.")
    monkeypatch.setattr(book_api.provider, "fetch_by_doi", fail)
    assert client.get("/book-metadata?doi=10.1234/book").status_code == 502
    assert create(client)["title"] == "Power systems"
