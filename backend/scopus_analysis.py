"""Transient Scopus CSV parsing and reconciliation for BibTeX analysis.

Nothing in this module persists uploaded data.  It adds source provenance and
review signals to the existing BibTeX analysis response only.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from .doi import normalize_doi
from .matching import normalized_name


class ScopusCSVError(ValueError):
    pass


MAX_SCOPUS_FIELD_LENGTH = 128_000
REQUIRED_HEADERS = {"eid", "title", "year", "document type"}
SPECIAL_TYPES = {"EDITORIAL", "ERRATUM", "RETRACTED", "RETRACTION", "RETRACTION NOTICE"}


def _header(value: str) -> str:
    return " ".join((value or "").replace("\ufeff", "").strip().casefold().split())


def _value(row: dict, *names: str) -> str:
    for name in names:
        value = row.get(_header(name))
        if value is not None:
            return value.strip()
    return ""


def _year(value: str) -> str:
    match = re.search(r"\b(\d{4})\b", value or "")
    return match.group(1) if match else ""


def _document_family(document_type: str) -> str:
    value = _header(document_type).upper()
    if value in {"ARTICLE", "REVIEW"}:
        return "JOURNAL"
    if value == "CONFERENCE PAPER":
        return "CONFERENCE"
    if value in {"BOOK", "BOOK CHAPTER"}:
        return "BOOKS_CHAPTERS"
    if value in SPECIAL_TYPES:
        return "SPECIAL"
    return "POLICY_REVIEW"


def _bibtex_family(entry: dict) -> str:
    entry_type = ((entry.get("publication") or {}).get("raw_metadata_json") or {}).get("bibtex", {}).get("entry_type", "").casefold()
    return {"article": "JOURNAL", "inproceedings": "CONFERENCE", "conference": "CONFERENCE", "book": "BOOKS_CHAPTERS"}.get(entry_type, "POLICY_REVIEW")


def _expected_scopus_types(entry_type: str) -> set[str]:
    return {
        "article": {"ARTICLE", "REVIEW"},
        "inproceedings": {"CONFERENCE PAPER"},
        "conference": {"CONFERENCE PAPER"},
        "book": {"BOOK"},
    }.get(entry_type.casefold(), set())


def _bibtex_type(entry: dict) -> str:
    return ((entry.get("publication") or {}).get("raw_metadata_json") or {}).get("bibtex", {}).get("entry_type", "UNKNOWN")


def _bibtex_venue(publication: dict) -> str:
    return publication.get("journal_conference_name") or publication.get("proceedings_title") or publication.get("conference_name") or ""


def _conflict(field: str, bibtex_value: str | None, scopus_value: str | None, assessment: str, severity: str) -> dict:
    return {"field": field, "bibtex_value": bibtex_value or None, "scopus_value": scopus_value or None, "assessment": assessment, "severity": severity}


def _source_conflicts(entry: dict, record: dict, method: str) -> list[dict]:
    """Compare sources without treating ordinary supplementary metadata as errors."""
    publication = entry.get("publication") or {}
    bib_type = _bibtex_type(entry)
    expected = _expected_scopus_types(bib_type)
    scopus_type = record["document_type"]
    conflicts = []
    if expected and _header(scopus_type).upper() not in expected:
        severity = "INFORMATIONAL" if _bibtex_family(entry) == "BOOKS_CHAPTERS" and _document_family(scopus_type) == "BOOKS_CHAPTERS" else "REQUIRES_REVIEW"
        conflicts.append(_conflict("Document type", bib_type, scopus_type, "Classification review", severity))
    bib_doi, csv_doi = publication.get("doi"), record.get("doi")
    if bib_doi and csv_doi and bib_doi != csv_doi:
        conflicts.append(_conflict("DOI", bib_doi, csv_doi, "Sources identify different DOI values", "IDENTITY_CONFLICT"))
    bib_title, csv_title = publication.get("title") or "", record.get("title") or ""
    if normalized_name(bib_title) and normalized_name(csv_title) and normalized_name(bib_title) != normalized_name(csv_title):
        ratio = SequenceMatcher(None, normalized_name(bib_title), normalized_name(csv_title)).ratio()
        severity = "IDENTITY_CONFLICT" if method == "DOI" and ratio < 0.70 else "REQUIRES_REVIEW"
        conflicts.append(_conflict("Title", bib_title, csv_title, "Title differs between sources", severity))
    bib_year, csv_year = str(entry.get("publication_year") or ""), str(record.get("year") or "")
    if bib_year and csv_year and bib_year != csv_year:
        conflicts.append(_conflict("Publication year", bib_year, csv_year, "Requires date verification", "REQUIRES_REVIEW"))
    bib_venue, csv_venue = _bibtex_venue(publication), record.get("source_title") or record.get("conference_name") or ""
    if bib_venue and csv_venue and normalized_name(bib_venue) != normalized_name(csv_venue):
        conflicts.append(_conflict("Venue", bib_venue, csv_venue, "Venue differs between sources", "REQUIRES_REVIEW"))
    elif not bib_venue and csv_venue:
        conflicts.append(_conflict("Venue", None, csv_venue, "Supplementary CSV metadata", "INFORMATIONAL"))
    bib_authors = "; ".join(author.get("author_name_from_source") or "" for author in publication.get("authors", []))
    csv_authors = record.get("authors") or ""
    if bib_authors and csv_authors and normalized_name(bib_authors) != normalized_name(csv_authors):
        conflicts.append(_conflict("Author list", bib_authors, csv_authors, "Author-list comparison requires review", "INFORMATIONAL"))
    return conflicts


def review_dimensions(entries: list[dict]) -> dict:
    """Count independent review dimensions after optional reconciliation."""
    duplicates = Counter(entry.get("duplicate_status") for entry in entries)
    metadata = Counter(entry.get("metadata_status") for entry in entries)
    dates = Counter(entry.get("publication_date_status") for entry in entries)
    classifications = Counter((entry.get("document_classification") or {}).get("suggested_module") for entry in entries)
    return {
        "duplicate_statuses": dict(duplicates),
        "metadata_statuses": dict(metadata),
        "date_statuses": dict(dates),
        "document_modules": dict(classifications),
        "missing_exact_publication_dates": dates["MISSING"],
        "missing_venues": sum("journal or conference" in entry.get("missing_metadata", []) for entry in entries),
        "valid_dois": sum(bool((entry.get("publication") or {}).get("doi")) for entry in entries),
        "missing_dois": sum(not bool((entry.get("publication") or {}).get("doi")) for entry in entries),
        "no_duplicate_detected": duplicates["NO_DUPLICATE_DETECTED"],
        "potentially_new_needs_review": sum(entry.get("duplicate_status") == "NO_DUPLICATE_DETECTED" and entry.get("metadata_status") == "NEEDS_REVIEW" for entry in entries),
    }


def parse_scopus_csv(content: str) -> list[dict]:
    """Read a Scopus CSV as text; spreadsheet formula syntax is never evaluated."""
    try:
        reader = csv.DictReader(io.StringIO(content), strict=True)
        if not reader.fieldnames:
            raise ScopusCSVError("The Scopus CSV has no header row.")
        headers = {_header(header): header for header in reader.fieldnames if header}
    except csv.Error as exc:
        raise ScopusCSVError("The Scopus CSV could not be read.") from exc
    missing = REQUIRED_HEADERS - set(headers)
    if missing:
        raise ScopusCSVError(f"The Scopus CSV is missing required headers: {', '.join(sorted(missing))}.")
    records = []
    try:
        for number, source in enumerate(reader, 1):
            row = {_header(key): (value or "").strip() for key, value in source.items() if key is not None}
            oversized = [key for key, value in row.items() if len(value) > MAX_SCOPUS_FIELD_LENGTH]
            if oversized:
                raise ScopusCSVError(f"CSV row {number} has an excessively long {oversized[0]} field.")
            raw_doi = _value(row, "doi")
            try:
                doi = normalize_doi(raw_doi)
            except ValueError:
                doi = None
            document_type = _value(row, "document type")
            formula_fields = [key for key, value in row.items() if value[:1] in {"=", "+", "-", "@"}]
            records.append({
                "source_row": number,
                "eid": _value(row, "eid"),
                "doi": doi,
                "raw_doi": raw_doi or None,
                "title": _value(row, "title"),
                "normalized_title": normalized_name(_value(row, "title")),
                "year": _year(_value(row, "year")),
                "document_type": document_type or "UNKNOWN",
                "source_title": _value(row, "source title"),
                "conference_name": _value(row, "conference name"),
                "conference_date": _value(row, "conference date"),
                "conference_location": _value(row, "conference location"),
                "publisher": _value(row, "publisher"),
                "issn": _value(row, "issn"),
                "isbn": _value(row, "isbn"),
                "article_number": _value(row, "article number"),
                "pages": _value(row, "page start", "page end", "pages"),
                "authors": _value(row, "authors"),
                "author_ids": _value(row, "author(s) id", "author ids"),
                "affiliations": _value(row, "affiliations"),
                "abstract": _value(row, "abstract"),
                "keywords": _value(row, "author keywords", "index keywords"),
                "citation_count_snapshot": _value(row, "cited by"),
                "funding": _value(row, "funding details", "funding text"),
                "formula_like_fields": formula_fields,
                "warnings": (["The CSV DOI is not valid and was not used for matching."] if raw_doi and not doi else []) +
                            (["Formula-like CSV cells are retained strictly as text."] if formula_fields else []),
            })
    except csv.Error as exc:
        raise ScopusCSVError("The Scopus CSV contains malformed rows.") from exc
    if not records:
        raise ScopusCSVError("The Scopus CSV is empty.")
    eid_counts = Counter(record["eid"] for record in records if record["eid"])
    doi_counts = Counter(record["doi"] for record in records if record["doi"])
    for record in records:
        if record["eid"] and eid_counts[record["eid"]] > 1:
            record["warnings"].append("The Scopus EID is repeated in this CSV; review the source rows.")
        if record["doi"] and doi_counts[record["doi"]] > 1:
            record["warnings"].append("The normalized Scopus DOI is repeated in this CSV; review the source rows.")
    return records


def reconcile_scopus_entries(entries: list[dict], records: list[dict]) -> dict:
    """Attach conservative, non-persisted Scopus source matches to BibTeX rows.

    A CSV row with two BibTeX candidates is deliberately represented on *both*
    sides.  Earlier versions only recorded it in ``unmatched_records``, which
    made the corresponding BibTeX rows look incorrectly ``BIBTEX_ONLY``.
    """
    bib_by_doi: dict[str, list[int]] = defaultdict(list)
    bib_by_title_year: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, entry in enumerate(entries):
        publication = entry.get("publication") or {}
        if publication.get("doi"):
            bib_by_doi[publication["doi"]].append(index)
        title, year = normalized_name(publication.get("title")), str(entry.get("publication_year") or "")
        if title and year:
            bib_by_title_year[(title, year)].append(index)

    candidates_by_bib: dict[int, list[dict]] = defaultdict(list)
    csv_results: list[dict] = []
    for record in records:
        candidates = bib_by_doi.get(record["doi"], []) if record["doi"] else []
        method = "DOI" if candidates else None
        if not candidates and record["normalized_title"] and record["year"]:
            candidates = bib_by_title_year.get((record["normalized_title"], record["year"]), [])
            method = "TITLE_YEAR" if candidates else None
        candidate_numbers = [entries[index]["entry_number"] for index in candidates]
        if not candidates:
            result = {**record, "match_method": None, "match_status": "CSV_ONLY", "candidate_entry_numbers": [], "ambiguity_reason": "NO_BIBTEX_CANDIDATE"}
        elif len(candidates) > 1:
            result = {**record, "match_method": method, "match_status": "AMBIGUOUS", "candidate_entry_numbers": candidate_numbers, "ambiguity_reason": "MULTIPLE_BIBTEX_CANDIDATES"}
        else:
            candidate = entries[candidates[0]]
            conflicts = _source_conflicts(candidate, record, method or "TITLE_YEAR")
            result = {**record, "match_method": method, "match_status": "CONFLICT" if conflicts else "MATCHED", "candidate_entry_numbers": candidate_numbers, "source_conflicts": conflicts, "ambiguity_reason": None}
        csv_results.append(result)
        for index in candidates:
            candidates_by_bib[index].append(result)

    statuses = Counter()
    field_conflicts, severity_conflicts = Counter(), Counter()
    for index, entry in enumerate(entries):
        source_records = candidates_by_bib.get(index, [])
        publication = entry.get("publication") or {}
        unique_records = [record for record in source_records if record["match_status"] in {"MATCHED", "CONFLICT"}]
        ambiguous_records = [record for record in source_records if record["match_status"] == "AMBIGUOUS"]
        if ambiguous_records or len(unique_records) > 1:
            status, selected, ambiguity_reason = "AMBIGUOUS", None, "MULTIPLE_SOURCE_CANDIDATES" if len(source_records) > 1 else ambiguous_records[0]["ambiguity_reason"]
        elif len(unique_records) == 1:
            selected, ambiguity_reason = unique_records[0], None
            status = selected["match_status"]
        else:
            status, selected, ambiguity_reason = "BIBTEX_ONLY", None, "NO_CSV_CANDIDATE"
        conflicts = [conflict for record in unique_records for conflict in record.get("source_conflicts", [])]
        for conflict in conflicts:
            field_conflicts[conflict["field"]] += 1
            severity_conflicts[conflict["severity"]] += 1
        bib_type = _bibtex_type(entry)
        scopus_type = selected["document_type"] if selected else None
        special = _header(scopus_type or "").upper() in SPECIAL_TYPES
        classification = {
            "bibtex_type": bib_type,
            "scopus_document_type": scopus_type,
            "suggested_module": _document_family(scopus_type) if scopus_type else _bibtex_family(entry),
            "classification_conflict": any(conflict["field"] == "Document type" for conflict in conflicts),
            "special_record": special,
        }
        duplicate = entry["duplicate_matches"]
        if duplicate["database_exact"]:
            duplicate_status = "EXISTING_DATABASE"
        elif duplicate["within_file_exact"]:
            duplicate_status = "DUPLICATE_WITHIN_UPLOAD"
        elif duplicate["database_possible"] or duplicate["within_file_possible"]:
            duplicate_status = "POSSIBLE_DUPLICATE"
        elif entry.get("errors"):
            duplicate_status = "UNDETERMINED"
        else:
            duplicate_status = "NO_DUPLICATE_DETECTED"
        if entry.get("errors"):
            metadata_status = "PARSE_ERROR"
        elif publication.get("publication_type") == "OTHER":
            metadata_status = "UNSUPPORTED"
        elif entry.get("missing_metadata") or any(author.get("matching_status") == "SUGGESTED" for author in publication.get("authors", [])):
            metadata_status = "NEEDS_REVIEW"
        else:
            metadata_status = "COMPLETE"
        date_status = "EXACT_BIBTEX" if publication.get("publication_date") else "MISSING"
        if duplicate_status == "EXISTING_DATABASE":
            eligibility = "DUPLICATE_REVIEW_EXISTING"
        elif special:
            eligibility = "NOT_ELIGIBLE_CURRENT_PUBLICATION_RULES"
        elif classification["suggested_module"] == "BOOKS_CHAPTERS" or classification["classification_conflict"] or any(conflict["severity"] == "IDENTITY_CONFLICT" for conflict in conflicts):
            eligibility = "REQUIRES_DOCUMENT_TYPE_REVIEW"
        elif metadata_status != "COMPLETE":
            eligibility = "REQUIRES_METADATA_COMPLETION"
        else:
            eligibility = "POTENTIALLY_ELIGIBLE_AFTER_REVIEW"
        entry.update({
            "scopus_match": {
                "status": status, "matches": source_records,
                "candidate_entry_numbers": sorted({number for record in source_records for number in record.get("candidate_entry_numbers", [])}),
                "csv_record": selected, "matching_evidence": {"method": selected.get("match_method") if selected else None, "candidate_csv_rows": [record["source_row"] for record in source_records], "candidate_scopus_eids": [record["eid"] for record in source_records], "ambiguity_reason": ambiguity_reason},
            },
            "document_classification": classification,
            "duplicate_status": duplicate_status,
            "metadata_status": metadata_status,
            "publication_date_status": date_status,
            "import_eligibility": eligibility,
            "source_conflicts": conflicts,
            "conference_suggestions": {
                "bibtex_booktitle": publication.get("proceedings_title"),
                "bibtex_journal_fallback": publication.get("journal_conference_name") if _bibtex_family(entry) == "CONFERENCE" else None,
                "csv_conference_name": selected.get("conference_name") if selected else None,
                "csv_source_title": selected.get("source_title") if selected else None,
            },
        })
        statuses[status] += 1
    csv_statuses = Counter(record["match_status"] for record in csv_results)
    duplicate_eids = Counter(record["eid"] for record in records if record["eid"])
    duplicate_csv_dois = Counter(record["doi"] for record in records if record["doi"])
    return {
        "records": records,
        "unmatched_records": [record for record in csv_results if record["match_status"] in {"CSV_ONLY", "AMBIGUOUS"}],
        "summary": {
            "total_csv_records": len(records),
            "total_bibtex_entries": len(entries),
            "unique_csv_matches": csv_statuses["MATCHED"] + csv_statuses["CONFLICT"],
            "unique_bibtex_matches": statuses["MATCHED"] + statuses["CONFLICT"],
            "ambiguous_bibtex_entries": statuses["AMBIGUOUS"],
            "bibtex_only_entries": statuses["BIBTEX_ONLY"],
            "csv_only_records": csv_statuses["CSV_ONLY"],
            "ambiguous_csv_records": csv_statuses["AMBIGUOUS"],
            "classification_conflicts": sum(1 for entry in entries if entry.get("document_classification", {}).get("classification_conflict")),
            "entries_with_source_conflicts": sum(bool(entry.get("source_conflicts")) for entry in entries),
            "conflict_fields": dict(field_conflicts),
            "conflict_severities": dict(severity_conflicts),
            "duplicate_csv_eids": sum(count > 1 for count in duplicate_eids.values()),
            "duplicate_csv_dois": sum(count > 1 for count in duplicate_csv_dois.values()),
        },
    }
