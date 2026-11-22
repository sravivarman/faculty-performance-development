from sqlalchemy import func, select

from backend import main
from backend.models import Publication
from conftest import paper


def upload(client, name, content):
    return client.post(
        "/publications/analyze-bibtex-file",
        files={"file": (name, content, "application/x-bibtex")},
    )


def entry(key, title, doi=None, venue="Energy Venue", date_value="2026-09-18", year_value="2026"):
    doi_field = f", doi={{{doi}}}" if doi else ""
    return f"@article{{{key}, title={{{title}}}, author={{Faculty, A}}, journal={{{venue}}}, year={{{year_value}}}, date={{{date_value}}}{doi_field}}}"


def test_file_analysis_uses_existing_parser_and_is_read_only(setup):
    client, factory, _ = setup
    existing = paper(None)
    existing.update(title="Existing Venue Paper", journal_conference_name="Energy Venue", publication_date="2026-09-18")
    created = client.post("/publications", json=existing)
    assert created.status_code == 201, created.text
    with factory() as db:
        publication = db.get(Publication, created.json()["id"])
        publication.doi = "10.1234/already-there"
        publication.is_active = False
        db.commit()
        count_before = db.scalar(select(func.count()).select_from(Publication))

    content = "\ufeff" + "\n".join([
        entry("doi-one", "Database DOI", "https://doi.org/10.1234/ALREADY-THERE"),
        entry("doi-two", "Repeated DOI", "DOI:10.1234/already-there"),
        entry("triple", "Existing Venue Paper"),
        entry("similar", "Existing Venue Pape"),
        entry("new", "A New Candidate", "10.1234/new-candidate"),
        "@misc{unsupported, title={Unsupported type}, year={2026}}",
        "@article{broken, author={Broken Author",
    ])
    response = upload(client, "faculty-publications.bib", content.encode("utf-8"))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["analysis_only"] is True and result["file_name"] == "faculty-publications.bib"
    assert result["total_entries"] == 7
    entries = {entry["citation_key"]: entry for entry in result["entries"]}
    assert entries["doi-one"]["primary_disposition"] == "ALREADY_IN_DATABASE"
    assert entries["doi-one"]["duplicate_matches"]["database_exact"][0]["is_active"] is False
    assert entries["doi-two"]["duplicate_matches"]["within_file_exact"][0]["citation_key"] == "doi-one"
    assert entries["triple"]["primary_disposition"] == "ALREADY_IN_DATABASE"
    assert entries["similar"]["primary_disposition"] == "POSSIBLE_DUPLICATE"
    assert entries["new"]["primary_disposition"] == "NEW_CANDIDATE"
    assert entries["unsupported"]["primary_disposition"] == "UNSUPPORTED_TYPE"
    assert any(entry["primary_disposition"] == "PARSE_ERROR" for entry in result["entries"])
    assert entries["new"]["publication"]["raw_bibtex"].startswith("@article{new")
    summary = result["summary"]
    assert sum(summary["primary_dispositions"].values()) == result["total_entries"]
    assert summary["possible_matches_in_database"] >= 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Publication)) == count_before


def test_file_analysis_handles_large_bom_upload_without_persisting(setup):
    client, factory, _ = setup
    content = "\ufeff" + "\n".join(entry(f"record{i}", f"Large upload record {i}", f"10.1234/large-{i}", year_value=str(1500 + i)) for i in range(560))
    response = upload(client, "large.bib", content.encode("utf-8"))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total_entries"] == result["summary"]["successfully_parsed"] == 560
    assert result["summary"]["new_candidates"] == 560
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Publication)) == 0


def test_file_analysis_rejects_invalid_files_with_clear_errors(setup, monkeypatch):
    client, _, _ = setup
    assert upload(client, "not-bib.txt", b"@article{x,title={Nope}}").status_code == 422
    assert "empty" in upload(client, "empty.bib", b" \n\t").json()["detail"].lower()
    assert "UTF-8" in upload(client, "bad.bib", b"\xff\xfe\x00").json()["detail"]
    monkeypatch.setattr(main, "BIBTEX_ANALYSIS_MAX_BYTES", 12)
    response = upload(client, "large.bib", b"@article{too-large}")
    assert response.status_code == 413 and "exceeds" in response.json()["detail"]


def test_file_analysis_marks_repeated_citation_keys_as_review_metadata(setup):
    client, _, _ = setup
    response = upload(client, "keys.bib", (entry("same-key", "First", "10.1234/one") + "\n" + entry("same-key", "Second", "10.1234/two")).encode())
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert [entry["citation_key"] for entry in entries] == ["same-key", "same-key"]
    assert [entry["publication"]["doi"] for entry in entries] == ["10.1234/one", "10.1234/two"]
    assert all(entry["repeated_citation_keys"] for entry in entries)
    assert all(entry["primary_disposition"] == "NEW_CANDIDATE" for entry in entries)


def test_file_analysis_normalizes_title_keys_and_marks_missing_year_for_review(setup):
    client, _, _ = setup
    content = "\n".join([
        entry("spaces-one", "Whitespace   Normalized", venue="Venue Name"),
        entry("spaces-two", " whitespace normalized ", venue=" venue   name "),
        "@article{no-year, title={Needs year}, author={Faculty, A}, journal={Energy Venue}, date={2026-09-18}}",
        entry("without-doi", "No DOI is still analyzable"),
    ])
    response = upload(client, "metadata.bib", content.encode())
    assert response.status_code == 200, response.text
    entries = {entry["citation_key"]: entry for entry in response.json()["entries"]}
    assert entries["spaces-one"]["primary_disposition"] == "DUPLICATE_WITHIN_FILE"
    assert entries["spaces-two"]["primary_disposition"] == "DUPLICATE_WITHIN_FILE"
    assert entries["no-year"]["primary_disposition"] == "NEEDS_METADATA_REVIEW"
    assert entries["without-doi"]["primary_disposition"] == "NEW_CANDIDATE"
