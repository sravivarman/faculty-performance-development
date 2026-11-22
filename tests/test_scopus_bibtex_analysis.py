from sqlalchemy import func, select

from backend import main
from backend.models import Publication
from backend.scopus_analysis import ScopusCSVError, parse_scopus_csv, reconcile_scopus_entries


def bibtex_entry(key, title, doi, year="2026", entry_type="article"):
    venue = "journal={Energy Venue}" if entry_type == "article" else "booktitle={Energy Proceedings}"
    return f"@{entry_type}{{{key}, title={{{title}}}, author={{Faculty, A and Researcher, B}}, {venue}, year={{{year}}}, doi={{{doi}}}}}"


def csv_row(eid, title, doi, year="2026", document_type="Article"):
    return f'"{eid}","{doi}","{title}","{year}","{document_type}","Energy Venue"'


def upload(client, bibtex, scopus=None):
    files = {"file": ("records.bib", bibtex.encode(), "application/x-bibtex")}
    if scopus is not None:
        files["scopus_file"] = ("scopus.csv", scopus.encode(), "text/csv")
    return client.post("/publications/analyze-bibtex-file", files=files)


def review_entry(number, title, doi, year="2026", entry_type="article"):
    return {
        "entry_number": number, "citation_key": f"entry-{number}", "publication_year": year, "errors": [], "missing_metadata": [],
        "duplicate_matches": {"database_exact": [], "within_file_exact": [], "database_possible": [], "within_file_possible": []},
        "publication": {"title": title, "doi": doi, "publication_type": "JOURNAL", "journal_conference_name": "Energy Venue", "authors": [], "raw_metadata_json": {"bibtex": {"entry_type": entry_type}}},
    }


def test_scopus_parser_marks_duplicate_source_rows_and_rejects_malformed_csv():
    source = "EID,DOI,Title,Year,Document Type\n" + "\n".join([
        "same,10.1234/same,First,2026,Article",
        "same,10.1234/same,Second,2026,Article",
    ])
    rows = parse_scopus_csv(source)
    assert all(any("repeated" in warning for warning in row["warnings"]) for row in rows)
    try:
        parse_scopus_csv('EID,DOI,Title,Year,Document Type\n"unterminated')
    except ScopusCSVError as exc:
        assert "malformed" in str(exc).lower()
    else:
        raise AssertionError("Malformed Scopus CSV must be rejected")


def test_reconciliation_attaches_ambiguous_csv_evidence_to_each_bibtex_candidate():
    entries = [review_entry(1, "Same identity", "10.1234/shared"), review_entry(2, "Same identity alternate", "10.1234/shared")]
    records = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n2-s2.0-1,10.1234/shared,Same identity,2026,Article")
    result = reconcile_scopus_entries(entries, records)
    assert result["summary"]["total_csv_records"] == 1
    assert result["summary"]["ambiguous_csv_records"] == 1
    assert result["summary"]["ambiguous_bibtex_entries"] == 2
    assert all(entry["scopus_match"]["status"] == "AMBIGUOUS" for entry in entries)
    assert all(entry["scopus_match"]["matching_evidence"]["candidate_scopus_eids"] == ["2-s2.0-1"] for entry in entries)


def test_reconciliation_marks_same_doi_material_title_difference_as_identity_conflict():
    entries = [review_entry(1, "A study of power electronics", "10.1234/correction")]
    records = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n2-s2.0-7,10.1234/correction,Correction to an unrelated article,2026,Article")
    reconcile_scopus_entries(entries, records)
    conflict = entries[0]["source_conflicts"]
    assert entries[0]["scopus_match"]["status"] == "CONFLICT"
    assert conflict[0]["field"] == "Title" and conflict[0]["severity"] == "IDENTITY_CONFLICT"


def test_reconciliation_source_counts_are_independent_and_complete():
    entries = [review_entry(1, "Matched", "10.1234/matched"), review_entry(2, "No CSV", "10.1234/no-csv")]
    records = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n2-s2.0-1,10.1234/matched,Matched,2026,Article\n2-s2.0-2,10.1234/csv-only,CSV only,2026,Article")
    summary = reconcile_scopus_entries(entries, records)["summary"]
    assert summary["unique_csv_matches"] + summary["ambiguous_csv_records"] + summary["csv_only_records"] == summary["total_csv_records"]
    assert summary["unique_bibtex_matches"] + summary["ambiguous_bibtex_entries"] + summary["bibtex_only_entries"] == summary["total_bibtex_entries"]


def test_combined_analysis_reconciles_doi_title_fallback_conflicts_and_csv_only_without_writing(setup):
    client, factory, _ = setup
    content = "\n".join([
        bibtex_entry("doi", "DOI match", "10.1234/doi-match"),
        bibtex_entry("fallback", "Fallback title", "10.1234/bib-only"),
        bibtex_entry("conflict", "Conflict source type", "10.1234/conflict"),
        bibtex_entry("unmatched", "BibTeX only", "10.1234/unmatched"),
    ])
    csv = "EID,DOI,Title,Year,Document Type,Source title\n" + "\n".join([
        csv_row("2-s2.0-1", "DOI match", "https://doi.org/10.1234/DOI-MATCH"),
        csv_row("2-s2.0-2", "Fallback title", "", document_type="Article"),
        csv_row("2-s2.0-3", "Conflict source type", "10.1234/conflict", document_type="Conference Paper"),
        csv_row("2-s2.0-4", "CSV only", "10.1234/csv-only", document_type="Review"),
    ])
    response = upload(client, content, csv)
    assert response.status_code == 200, response.text
    result = response.json()
    entries = {item["citation_key"]: item for item in result["entries"]}
    assert entries["doi"]["scopus_match"]["status"] == "MATCHED"
    assert entries["fallback"]["scopus_match"]["status"] == "MATCHED"
    assert entries["fallback"]["scopus_match"]["matches"][0]["match_method"] == "TITLE_YEAR"
    assert entries["conflict"]["scopus_match"]["status"] == "CONFLICT"
    assert entries["conflict"]["document_classification"]["classification_conflict"] is True
    assert entries["unmatched"]["scopus_match"]["status"] == "BIBTEX_ONLY"
    assert result["scopus"]["summary"]["csv_only_records"] == 1
    assert all(item["duplicate_status"] == "NO_DUPLICATE_DETECTED" for item in entries.values())
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Publication)) == 0


def test_combined_analysis_marks_ambiguous_doi_and_preserves_csv_as_text(setup):
    client, _, _ = setup
    content = "\n".join([bibtex_entry("one", "First duplicate DOI", "10.1234/shared"), bibtex_entry("two", "Second duplicate DOI", "10.1234/shared")])
    csv = "EID,DOI,Title,Year,Document Type,Source title\n" + csv_row("=not-a-formula", "Formula title", "10.1234/shared")
    response = upload(client, content, csv)
    assert response.status_code == 200, response.text
    result = response.json()
    assert [item["scopus_match"]["status"] for item in result["entries"]] == ["AMBIGUOUS", "AMBIGUOUS"]
    assert result["scopus"]["summary"]["ambiguous_csv_records"] == 1
    assert result["scopus"]["summary"]["ambiguous_bibtex_entries"] == 2
    record = result["scopus"]["unmatched_records"][0]
    assert record["eid"] == "=not-a-formula"
    assert "Formula-like CSV cells are retained strictly as text." in record["warnings"]


def test_scopus_csv_validation_rejects_invalid_file_encoding_and_headers(setup):
    client, _, _ = setup
    bibtex = bibtex_entry("one", "Valid BibTeX", "10.1234/valid")
    wrong_extension = client.post("/publications/analyze-bibtex-file", files={"file": ("records.bib", bibtex, "application/x-bibtex"), "scopus_file": ("records.txt", "x", "text/plain")})
    assert wrong_extension.status_code == 422 and ".csv" in wrong_extension.json()["detail"]
    missing_headers = upload(client, bibtex, "DOI,Title\n10.1234/valid,Valid BibTeX")
    assert missing_headers.status_code == 422 and "required headers" in missing_headers.json()["detail"]
    invalid_encoding = client.post("/publications/analyze-bibtex-file", files={"file": ("records.bib", bibtex, "application/x-bibtex"), "scopus_file": ("records.csv", b"\xff\xfe", "text/csv")})
    assert invalid_encoding.status_code == 422 and "UTF-8" in invalid_encoding.json()["detail"]


def test_explicit_date_enrichment_returns_candidates_without_persisting(setup, monkeypatch):
    client, factory, _ = setup

    class Provider:
        def fetch_by_doi(self, doi):
            return {"raw_metadata_json": {"message": {"published-online": {"date-parts": [[2026, 9, 4]]}, "published-print": {"date-parts": [[2026, 10]]}, "issued": {"date-parts": [[2026]]}}}}

    monkeypatch.setattr(main, "provider", Provider())
    response = client.post("/publications/analyze-bibtex-file/enrich-dates", json={"entries": [{"entry_number": 1, "doi": "10.1234/date-test"}]})
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "FOUND" and result["preferred"] == {"date": "2026-09-04", "precision": "DAY", "date_type": "ONLINE", "source_field": "published-online", "is_exact_online": True}
    assert result["alternatives"][1]["date"] == "2026-10"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Publication)) == 0


def test_date_enrichment_preserves_partial_dates_and_flags_provider_identity_difference(setup, monkeypatch):
    client, _, _ = setup

    class Provider:
        def fetch_by_doi(self, doi):
            return {"raw_metadata_json": {"message": {"title": ["Provider title differs"], "published-print": {"date-parts": [[2025, 6]]}, "issued": {"date-parts": [[2025]]}}}}

    monkeypatch.setattr(main, "provider", Provider())
    response = client.post("/publications/analyze-bibtex-file/enrich-dates", json={"entries": [{"entry_number": 2, "doi": "10.1234/identity", "title": "Uploaded title", "publication_year": "2026", "bibtex_date": "2026-01-15"}]})
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "IDENTITY_CONFLICT"
    assert result["preferred"] == {"date": "2025-06", "precision": "MONTH", "date_type": "PRINT", "source_field": "published-print", "is_exact_online": False}
    assert {conflict["field"] for conflict in result["identity_conflicts"]} == {"Title", "Publication year"}
    assert result["bibtex_date_conflict"] is True


def test_date_enrichment_enforces_25_request_cap(setup):
    client, _, _ = setup
    response = client.post("/publications/analyze-bibtex-file/enrich-dates", json={"entries": [{"entry_number": index, "doi": f"10.1234/cap-{index}"} for index in range(1, 27)]})
    assert response.status_code == 422, response.text
