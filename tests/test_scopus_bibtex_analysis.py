from datetime import date

from sqlalchemy import func, select

from backend import main
from backend.models import Department, FacultyDepartmentAffiliation, Publication, PublicationAuthor
from backend.scopus_analysis import ScopusCSVError, parse_scopus_csv, reconcile_scopus_entries, review_dimensions


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
    assert entries[0]["scopus_match"]["status"] == "IDENTITY_CONFLICT"
    assert conflict[0]["reason_code"] == "TITLE_DIFFERENCE" and conflict[0]["severity"] == "IDENTITY_CONFLICT"


def test_reconciliation_accepts_conservative_full_name_and_initials_formatting():
    entry = review_entry(1, "Author compatibility", "10.1234/authors")
    entry["publication"]["authors"] = [
        {"author_name_from_source": "Praveen Kumar Balachandran"},
        {"author_name_from_source": "Anuradha Devi"},
    ]
    record = parse_scopus_csv("EID,DOI,Title,Year,Document Type,Authors\n2-s2.0-a,10.1234/authors,Author compatibility,2026,Article,Balachandran P.K.; Devi A.")[0]
    reconcile_scopus_entries([entry], [record])
    assert entry["scopus_match"]["status"] == "MATCHED"
    assert entry["scopus_match"]["metadata_comparison"] == "CONSISTENT"
    assert entry["source_conflicts"] == []


def test_reconciliation_keeps_author_order_difference_separate_from_identity():
    entry = review_entry(1, "Author order", "10.1234/order")
    entry["publication"]["authors"] = [
        {"author_name_from_source": "Praveen Kumar Balachandran"},
        {"author_name_from_source": "Anuradha Devi"},
    ]
    record = parse_scopus_csv("EID,DOI,Title,Year,Document Type,Authors\n2-s2.0-b,10.1234/order,Author order,2026,Article,Devi A.; Balachandran P.K.")[0]
    reconcile_scopus_entries([entry], [record])
    assert entry["scopus_match"]["status"] == "MATCHED"
    assert entry["scopus_match"]["metadata_comparison"] == "REQUIRES_REVIEW"
    assert entry["source_conflicts"][0]["reason_code"] == "AUTHOR_ORDER_DIFFERENCE"


def test_supplementary_source_venue_is_informational_not_an_identity_conflict():
    entry = review_entry(1, "Supplementary venue", "10.1234/venue")
    entry["publication"]["journal_conference_name"] = None
    record = parse_scopus_csv("EID,DOI,Title,Year,Document Type,Source title\n2-s2.0-v,10.1234/venue,Supplementary venue,2026,Article,Scopus Source Journal")[0]
    reconcile_scopus_entries([entry], [record])
    assert entry["scopus_match"]["status"] == "MATCHED"
    assert entry["scopus_match"]["metadata_comparison"] == "INFORMATIONAL_DIFFERENCES"
    assert entry["source_conflicts"][0]["reason_code"] == "SUPPLEMENTARY_METADATA"


def test_conference_proceedings_metadata_is_not_reported_as_missing_venue():
    entry = review_entry(1, "Reddy-style conference", "10.1063/5.0317499", entry_type="inproceedings")
    entry["publication"].update({"publication_type": "CONFERENCE", "journal_conference_name": "AIP Conference Proceedings", "proceedings_title": "AIP Conference Proceedings", "conference_name": None})
    record = parse_scopus_csv("EID,DOI,Title,Year,Document Type,Source title,Conference name,Conference date,Publisher\n2-s2.0-c,10.1063/5.0317499,Reddy-style conference,2026,Conference Paper,AIP Conference Proceedings,ICIATI 2023,June 2023,AIP")[0]
    reconcile_scopus_entries([entry], [record])
    suggestions = entry["conference_suggestions"]
    assert entry["scopus_match"]["status"] == "MATCHED"
    assert suggestions["proceedings_title"] == "AIP Conference Proceedings"
    assert suggestions["conference_name"] == "ICIATI 2023"
    assert suggestions["conference_date"] == "June 2023"


def test_import_readiness_keeps_duplicate_date_and_claimant_reasons_independent():
    entry = review_entry(1, "Readiness", "10.1234/readiness")
    entry["publication"]["authors"] = [{"author_name_from_source": "Faculty A", "person_type": "FACULTY", "faculty_id": 1, "matching_status": "EXACT"}]
    record = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n2-s2.0-r,10.1234/readiness,Readiness,2026,Article")[0]
    reconcile_scopus_entries([entry], [record])
    readiness = entry["import_readiness"]
    assert entry["duplicate_status"] == "NO_DUPLICATE_DETECTED"
    assert readiness["status"] == "DATE_VERIFICATION_REQUIRED"
    assert readiness["blockers"] == ["DATE_VERIFICATION_REQUIRED"]
    assert readiness["claimant_candidates"] == [{"faculty_id": 1, "name": "Faculty A", "confidence": None, "matching_status": "EXACT", "department": None}]


def test_import_readiness_flags_year_only_date_and_unresolved_internal_author():
    entry = review_entry(1, "Year only", "10.1234/year-only")
    entry["publication"]["authors"] = [{"author_name_from_source": "Potential VCE Author", "person_type": "UNKNOWN", "matching_status": "SUGGESTED", "affiliation_from_source": ["Vardhaman College of Engineering"]}]
    record = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n2-s2.0-y,10.1234/year-only,Year only,2026,Article")[0]
    reconcile_scopus_entries([entry], [record])
    readiness = entry["import_readiness"]
    assert "DATE_VERIFICATION_REQUIRED" in readiness["blockers"]
    assert "CONTRIBUTOR_REVIEW_REQUIRED" in readiness["blockers"]
    assert "CLAIMANT_REQUIRED" in readiness["blockers"]


def test_import_readiness_marks_complete_supported_record_ready_for_human_review():
    entry = review_entry(1, "Complete record", "10.1234/complete")
    entry["publication"]["publication_date"] = "2026-09-04"
    entry["publication"]["authors"] = [{"author_name_from_source": "Faculty A", "person_type": "FACULTY", "faculty_id": 1, "matching_status": "EXACT"}]
    record = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n2-s2.0-complete,10.1234/complete,Complete record,2026,Article")[0]
    reconcile_scopus_entries([entry], [record])
    assert entry["publication_date_status"] == "EXACT_BIBTEX"
    assert entry["import_readiness"]["status"] == "READY_FOR_REVIEW"
    assert entry["import_readiness"]["blockers"] == []


def test_import_readiness_retains_books_and_special_record_policy_blockers():
    book = review_entry(1, "Book record", "10.1234/book", entry_type="book")
    special = review_entry(2, "Editorial record", "10.1234/editorial")
    for entry in (book, special):
        entry["publication"]["publication_date"] = "2026-09-04"
        entry["publication"]["authors"] = [{"author_name_from_source": "Faculty A", "person_type": "FACULTY", "faculty_id": 1, "matching_status": "EXACT"}]
    records = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n"
                               "2-s2.0-book,10.1234/book,Book record,2026,Book\n"
                               "2-s2.0-editorial,10.1234/editorial,Editorial record,2026,Editorial")
    reconcile_scopus_entries([book, special], records)
    assert "CLASSIFICATION_REVIEW_REQUIRED" in book["import_readiness"]["blockers"]
    assert "SPECIAL_RECORD_POLICY_REVIEW" in special["import_readiness"]["blockers"]


def test_readiness_summary_uses_non_duplicate_candidate_scope_with_populated_counters():
    complete = review_entry(1, "Complete candidate", "10.1234/complete-summary")
    missing_date = review_entry(2, "Missing-date candidate", "10.1234/missing-summary")
    special = review_entry(3, "Special candidate", "10.1234/special-summary")
    existing = review_entry(4, "Existing duplicate", "10.1234/existing-summary")
    for entry in (complete, missing_date, special, existing):
        entry["publication"]["authors"] = [{"author_name_from_source": "Faculty A", "person_type": "FACULTY", "faculty_id": 1, "matching_status": "EXACT"}]
    complete["publication"]["publication_date"] = "2026-09-04"
    special["publication"]["publication_date"] = "2026-09-04"
    existing["publication"]["publication_date"] = "2026-09-04"
    existing["duplicate_matches"]["database_exact"] = [{"publication_id": 99}]
    records = parse_scopus_csv("EID,DOI,Title,Year,Document Type\n"
                               "2-s2.0-complete,10.1234/complete-summary,Complete candidate,2026,Article\n"
                               "2-s2.0-missing,10.1234/missing-summary,Missing-date candidate,2026,Article\n"
                               "2-s2.0-special,10.1234/special-summary,Special candidate,2026,Editorial\n"
                               "2-s2.0-existing,10.1234/existing-summary,Existing duplicate,2026,Article")
    reconcile_scopus_entries([complete, missing_date, special, existing], records)
    dimensions = review_dimensions([complete, missing_date, special, existing])
    summary = dimensions["readiness_summary"]
    assert summary["all_records"]["total"] == 4
    assert summary["potentially_new"]["total"] == 3
    assert summary["potentially_new"]["statuses"]["READY_FOR_REVIEW"] == 1
    assert summary["potentially_new"]["blockers"]["DATE_VERIFICATION_REQUIRED"] == 1
    assert summary["potentially_new"]["blockers"]["SPECIAL_RECORD_POLICY_REVIEW"] == 1
    assert summary["all_records"]["blockers"]["DUPLICATE_EXISTING"] == 1
    # The legacy flat fields remain available to existing API consumers.
    assert dimensions["potentially_new"] == 3
    assert dimensions["readiness_blockers"]["DUPLICATE_EXISTING"] == 1


def test_import_readiness_exposes_current_faculty_department_without_inferring_history(setup):
    client, factory, _ = setup
    with factory() as db:
        # The Department migration seeds EEE and gives pre-existing Faculty a
        # current baseline affiliation. Reuse that fixture data when present.
        department = db.scalar(select(Department).where(Department.code == "EEE"))
        if department is None:
            department = Department(code="EEE", name="Electrical and Electronics Engineering")
            db.add(department); db.flush()
        department_id = department.id
        affiliation = db.scalar(select(FacultyDepartmentAffiliation).where(
            FacultyDepartmentAffiliation.faculty_id == 1,
            FacultyDepartmentAffiliation.is_primary.is_(True),
            FacultyDepartmentAffiliation.effective_to.is_(None),
        ))
        if affiliation is None:
            affiliation = FacultyDepartmentAffiliation(faculty_id=1, department_id=department_id, effective_from=None,
                                                       effective_to=None, is_primary=True, source="MIGRATION_BASELINE")
            db.add(affiliation)
        db.commit()

    response = upload(client, bibtex_entry("department", "Department context", "10.1234/department"))
    assert response.status_code == 200, response.text
    candidate = response.json()["entries"][0]["import_readiness"]["claimant_candidates"][0]
    assert candidate["faculty_id"] == 1
    assert candidate["department"] == {"id": department_id, "code": "EEE", "name": "Electrical and Electronics Engineering"}
    # A baseline affiliation deliberately has no fabricated historical start.
    assert affiliation.effective_from is None
    assert affiliation.source == "MIGRATION_BASELINE"


def test_existing_duplicate_reports_saved_claimant_without_modifying_it(setup):
    client, factory, _ = setup
    with factory() as db:
        existing = Publication(title="Saved publication", doi="10.1234/saved", publication_type="JOURNAL",
                               journal_conference_name="Energy Venue", publication_date=date(2026, 9, 4),
                               indexing=[], classification="UNKNOWN", source_type="MANUAL", metadata_source="MANUAL",
                               is_claimable=True, is_active=True)
        existing.authors = [PublicationAuthor(author_order=1, author_name_from_source="Faculty A", person_type="FACULTY",
                                               faculty_id=1, is_internal=True, is_claiming_faculty=True, matching_status="EXACT")]
        db.add(existing); db.commit()
        publication_id = existing.id

    response = upload(client, bibtex_entry("saved", "Saved publication", "10.1234/saved"))
    assert response.status_code == 200, response.text
    match = response.json()["entries"][0]["duplicate_matches"]["database_exact"][0]
    assert match["publication_id"] == publication_id
    assert match["claiming_faculty"] == {"faculty_id": 1, "name": "Faculty A"}
    with factory() as db:
        assert db.get(Publication, publication_id).authors[0].is_claiming_faculty is True


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
    assert entries["conflict"]["scopus_match"]["status"] == "MATCHED"
    assert entries["conflict"]["document_classification"]["classification_conflict"] is True
    assert entries["conflict"]["scopus_match"]["metadata_comparison"] == "REQUIRES_REVIEW"
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

    class Verifier:
        def __init__(self, _provider):
            pass

        def close(self):
            pass

        def verify(self, doi, **_kwargs):
            candidate = {"date": "2025-06", "precision": "MONTH", "date_type": "PRINT_PUBLICATION", "source": "CROSSREF", "source_field": "published-print", "source_url": "https://api.crossref.org/example", "assessment": "PRINT_ONLY"}
            return {"doi": doi, "identity_status": "IDENTITY_CONFLICT", "candidates": [candidate, {**candidate, "date": "2025", "precision": "YEAR", "source_field": "issued"}], "suggested_date": candidate, "suggestion_status": "PARTIAL_DATE_FOUND", "requires_review": True, "provider_failures": [], "bibtex_date_conflict": True}

    monkeypatch.setattr(main, "date_verifier_factory", Verifier)
    response = client.post("/publications/analyze-bibtex-file/enrich-dates", json={"entries": [{"entry_number": 2, "doi": "10.1234/identity", "title": "Uploaded title", "publication_year": "2026", "bibtex_date": "2026-01-15"}]})
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "FOUND"
    assert result["preferred"] == {"date": "2025-06", "precision": "MONTH", "date_type": "PRINT", "source_field": "published-print", "is_exact_online": False}
    assert result["verification"]["identity_status"] == "IDENTITY_CONFLICT"
    assert result["bibtex_date_conflict"] is True


def test_date_enrichment_enforces_25_request_cap(setup):
    client, _, _ = setup
    response = client.post("/publications/analyze-bibtex-file/enrich-dates", json={"entries": [{"entry_number": index, "doi": f"10.1234/cap-{index}"} for index in range(1, 27)]})
    assert response.status_code == 422, response.text
