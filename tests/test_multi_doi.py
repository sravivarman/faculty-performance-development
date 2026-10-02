import pytest
from sqlalchemy import func, select

from backend import main
from backend.doi import parse_doi_input
from backend.metadata import MetadataError, parse_crossref
from backend.models import Publication
from conftest import paper


@pytest.mark.parametrize("content,expected", [
    ("10.1234/one", ["10.1234/one"]),
    ("10.1234/one\n10.1234/two", ["10.1234/one", "10.1234/two"]),
    ("10.1234/one,10.1234/two", ["10.1234/one", "10.1234/two"]),
    ("10.1234/one;10.1234/two", ["10.1234/one", "10.1234/two"]),
    ("https://doi.org/10.1234/ONE\ndoi:10.1234/TWO", ["10.1234/one", "10.1234/two"]),
    ("10.1234/one,https://doi.org/10.1234/ONE;DOI:10.1234/one", ["10.1234/one"]),
    (" \r\n,; 10.1234/one \n ;", ["10.1234/one"]),
    ("https://doi.org/10.1234%2FONE", ["10.1234/one"]),
    (" \n,; ", []),
])
def test_pasted_doi_normalization(content, expected):
    assert [entry["doi"] for entry in parse_doi_input(content)] == expected


def test_invalid_identifiers_are_independent_and_deduplicated():
    entries = parse_doi_input("bad;10.1234/one;BAD;10.12/x;10.1234/two")
    assert [entry["status"] for entry in entries] == ["INVALID_DOI", "PENDING", "INVALID_DOI", "PENDING"]
    assert [entry["doi"] for entry in entries if entry["doi"]] == ["10.1234/one", "10.1234/two"]


class BatchProvider:
    def __init__(self):
        self.calls = []

    def fetch_by_doi(self, doi):
        self.calls.append(doi)
        if doi.endswith("/failed"):
            raise MetadataError("Provider failed for this DOI")
        conference = doi.endswith("/conference")
        return parse_crossref({"message": {
            "DOI": doi, "title": ["Preview " + doi],
            "type": "proceedings-article" if conference else "journal-article",
            "container-title": ["Proceedings" if conference else "Journal"],
            "published": {"date-parts": [[2026, 9, 18]]},
            "author": [{"name": "Faculty A"}, {"name": "Faculty B"},
                       {"name": "Student X"}, {"name": "Independent Researcher"}],
        }}, doi)


def test_existing_doi_is_duplicate_without_metadata_request(setup, monkeypatch):
    client, _, _ = setup
    existing = client.post("/publications", json=paper()).json()
    provider = BatchProvider()
    monkeypatch.setattr(main, "provider", provider)
    entries = client.post("/publications/parse-dois", json={"content": "https://doi.org/10.1234/P1;10.1234/p1"}).json()["entries"]
    assert len(entries) == 1
    response = client.get("/publications/lookup-doi", params={"doi": entries[0]["doi"]})
    assert response.status_code == 409
    assert response.json()["detail"]["publication_id"] == existing["id"]
    assert provider.calls == []


def test_failed_doi_does_not_prevent_mixed_previews_or_write_to_database(setup, monkeypatch):
    client, factory, _ = setup
    provider = BatchProvider()
    monkeypatch.setattr(main, "provider", provider)
    entries = client.post("/publications/parse-dois", json={"content": "10.1234/journal\n10.1234/failed\n10.1234/conference"}).json()["entries"]
    results = [client.get("/publications/lookup-doi", params={"doi": row["doi"]}) for row in entries]
    assert [r.status_code for r in results] == [200, 502, 200]
    assert [results[i].json()["publication_type"] for i in (0, 2)] == ["JOURNAL", "CONFERENCE"]
    for i in (0, 2):
        authors = results[i].json()["authors"]
        assert len(authors) == 4
        assert [(a["person_type"], a.get("faculty_id"), a.get("student_id")) for a in authors[:3]] == [("FACULTY", 1, None), ("FACULTY", 2, None), ("STUDENT", None, 1)]
        assert not any(a["is_claiming_faculty"] for a in authors)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Publication)) == 0


def test_independent_save_transactions_claimants_and_kpis(setup):
    client, factory, _ = setup
    first = paper("10.1234/journal")
    first.update(impact_factor=3.5, quartile="Q1")
    invalid = paper("10.1234/invalid-save")
    invalid["authors"][0]["faculty_id"] = 99999
    second = paper("10.1234/conference")
    second.update(publication_type="CONFERENCE", conference_name="Conference", indexing=["ESCI"], impact_factor=None, quartile="Q3")
    second["authors"][0]["is_claiming_faculty"] = False
    second["authors"][1]["is_claiming_faculty"] = True
    responses = [client.post("/publications", json=p) for p in (first, invalid, second)]
    assert responses[0].status_code == responses[2].status_code == 201
    assert responses[1].status_code == 422
    records = [responses[i].json() for i in (0, 2)]
    assert [[a["faculty_id"] for a in p["authors"] if a["is_claiming_faculty"]] for p in records] == [[1], [2]]
    assert [(p["impact_factor"], p["quartile"], p["indexing"]) for p in records] == [(3.5, "Q1", ["SCOPUS", "SCI", "SCIE"]), (None, "Q3", ["ESCI"])]
    with factory() as db:
        assert set(db.scalars(select(Publication.doi))) == {"10.1234/journal", "10.1234/conference"}
