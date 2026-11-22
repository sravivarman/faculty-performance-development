"""Transient Scopus CSV parsing and reconciliation for BibTeX analysis.

Nothing in this module persists uploaded data.  It adds source provenance and
review signals to the existing BibTeX analysis response only.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
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


def _difference(field: str, code: str, bibtex_value: str | None, scopus_value: str | None, assessment: str, severity: str) -> dict:
    """A non-persistent, field-level source comparison result.

    ``severity`` deliberately describes the metadata comparison, not source
    identity.  A matching DOI/title pair may therefore carry informational or
    reviewable differences while remaining ``MATCHED``.
    """
    return {"field": field, "reason_code": code, "bibtex_value": bibtex_value or None,
            "scopus_value": scopus_value or None, "assessment": assessment, "severity": severity}


_SURNAME_PARTICLES = {"da", "de", "del", "der", "di", "dos", "la", "le", "van", "von"}


def _author_parts(value: str) -> tuple[str, str]:
    """Return a conservative ``(family, given-initials)`` comparison key.

    This intentionally does not try to expand initials or identify a person;
    it merely accepts well-supported source formatting variants.
    """
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = re.sub(r"[.\-']", " ", normalized.casefold())
    normalized = re.sub(r"[^\w\s,]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return "", ""
    if "," in normalized:
        family, given = (part.strip() for part in normalized.split(",", 1))
        return family.replace(" ", ""), "".join(part[0] for part in given.split() if part)
    parts = normalized.split()
    # Scopus commonly writes ``Surname P.K.``.  Treat this format separately
    # from an ordinary given-name-first BibTeX rendering.
    if len(parts) > 1 and len(parts[0]) > 1 and all(len(part) == 1 for part in parts[1:]):
        return parts[0], "".join(parts[1:])
    family_start = len(parts) - 1
    while family_start > 0 and parts[family_start - 1] in _SURNAME_PARTICLES:
        family_start -= 1
    family = "".join(parts[family_start:])
    given = "".join(part[0] for part in parts[:family_start] if part)
    return family, given


def _author_list(value: str) -> list[tuple[str, str]]:
    return [_author_parts(name) for name in re.split(r"\s*;\s*|\s+and\s+", value or "") if name.strip()]


def _authors_compatible(left: tuple[str, str], right: tuple[str, str]) -> bool:
    left_family, left_initials = left
    right_family, right_initials = right
    if not left_family or left_family != right_family:
        return False
    # One source may omit all given-name detail, but one non-matching initial
    # is not enough evidence to call people equivalent.
    return not left_initials or not right_initials or left_initials == right_initials


def _source_differences(entry: dict, record: dict, method: str) -> list[dict]:
    """Compare sources without conflating metadata and publication identity."""
    publication = entry.get("publication") or {}
    bib_type = _bibtex_type(entry)
    expected = _expected_scopus_types(bib_type)
    scopus_type = record["document_type"]
    differences = []
    if expected and _header(scopus_type).upper() not in expected:
        severity = "INFORMATIONAL" if _bibtex_family(entry) == "BOOKS_CHAPTERS" and _document_family(scopus_type) == "BOOKS_CHAPTERS" else "REQUIRES_REVIEW"
        differences.append(_difference("Document type", "DOCUMENT_TYPE_DIFFERENCE", bib_type, scopus_type, "Classification review", severity))
    bib_doi, csv_doi = publication.get("doi"), record.get("doi")
    if bib_doi and csv_doi and bib_doi != csv_doi:
        differences.append(_difference("DOI", "DOI_DIFFERENCE", bib_doi, csv_doi, "Sources identify different DOI values", "IDENTITY_CONFLICT"))
    bib_title, csv_title = publication.get("title") or "", record.get("title") or ""
    if normalized_name(bib_title) and normalized_name(csv_title) and normalized_name(bib_title) != normalized_name(csv_title):
        ratio = SequenceMatcher(None, normalized_name(bib_title), normalized_name(csv_title)).ratio()
        severity = "IDENTITY_CONFLICT" if method == "DOI" and ratio < 0.70 else "REQUIRES_REVIEW"
        differences.append(_difference("Title", "TITLE_DIFFERENCE", bib_title, csv_title, "Title differs between sources", severity))
    bib_year, csv_year = str(entry.get("publication_year") or ""), str(record.get("year") or "")
    if bib_year and csv_year and bib_year != csv_year:
        differences.append(_difference("Publication year", "PUBLICATION_YEAR_DIFFERENCE", bib_year, csv_year, "Requires date verification", "REQUIRES_REVIEW"))
    bib_venue, csv_venue = _bibtex_venue(publication), record.get("source_title") or record.get("conference_name") or ""
    if bib_venue and csv_venue and normalized_name(bib_venue) != normalized_name(csv_venue):
        differences.append(_difference("Venue", "VENUE_DIFFERENCE", bib_venue, csv_venue, "Venue differs between sources", "REQUIRES_REVIEW"))
    elif not bib_venue and csv_venue:
        differences.append(_difference("Venue", "SUPPLEMENTARY_METADATA", None, csv_venue, "Supplementary CSV metadata", "INFORMATIONAL"))
    bib_authors = "; ".join(author.get("author_name_from_source") or "" for author in publication.get("authors", []))
    csv_authors = record.get("authors") or ""
    if bib_authors and csv_authors:
        bib_list, csv_list = _author_list(bib_authors), _author_list(csv_authors)
        if len(bib_list) != len(csv_list):
            differences.append(_difference("Author list", "AUTHOR_IDENTITY_DIFFERENCE", bib_authors, csv_authors, "Author counts differ between sources", "REQUIRES_REVIEW"))
        elif all(_authors_compatible(left, right) for left, right in zip(bib_list, csv_list)):
            pass  # Initial/full-name and punctuation variations are compatible.
        elif sorted(bib_list) == sorted(csv_list):
            differences.append(_difference("Author list", "AUTHOR_ORDER_DIFFERENCE", bib_authors, csv_authors, "Compatible authors appear in a different order", "REQUIRES_REVIEW"))
        else:
            differences.append(_difference("Author list", "AUTHOR_IDENTITY_DIFFERENCE", bib_authors, csv_authors, "Author identity cannot be established conservatively", "REQUIRES_REVIEW"))
    elif bib_authors or csv_authors:
        differences.append(_difference("Author list", "SUPPLEMENTARY_METADATA", bib_authors, csv_authors, "One source provides author metadata not present in the other", "INFORMATIONAL"))
    return differences


def _metadata_comparison(differences: list[dict]) -> str:
    if any(item["severity"] == "IDENTITY_CONFLICT" for item in differences):
        return "IDENTITY_CONFLICT"
    if any(item["severity"] == "REQUIRES_REVIEW" for item in differences):
        return "REQUIRES_REVIEW"
    if differences:
        return "INFORMATIONAL_DIFFERENCES"
    return "CONSISTENT"


def _import_readiness(entry: dict, classification: dict, duplicate_status: str, source_status: str, metadata_status: str, date_status: str) -> dict:
    """Derive a review plan using the existing single-publication save rules.

    This is deliberately a transient explanation of what would need human
    review later; it never prepares or saves a publication payload.
    """
    publication = entry.get("publication") or {}
    authors = publication.get("authors") or []
    faculty = [author for author in authors if author.get("person_type") == "FACULTY" and author.get("faculty_id") and author.get("matching_status") != "SUGGESTED"]
    students = [author for author in authors if author.get("person_type") == "STUDENT" and author.get("student_id") and author.get("matching_status") != "SUGGESTED"]
    unresolved_internal = [author for author in authors if author.get("person_type") == "UNKNOWN" and any(re.search(r"\bvardh?aman\b", value or "", re.I) for value in author.get("affiliation_from_source") or [])]
    external_or_unmatched = [author for author in authors if author.get("person_type") in {"EXTERNAL", "UNKNOWN"}]
    candidates = [{"faculty_id": author["faculty_id"], "name": author.get("person_name") or author.get("author_name_from_source"),
                   "confidence": author.get("matching_confidence"), "matching_status": author.get("matching_status"),
                   # This is existing current Master data only.  An
                   # activity-date Department is intentionally not inferred
                   # until a later human review has a verified date.
                   "department": author.get("department")} for author in faculty]
    blockers, warnings = [], []
    if duplicate_status == "EXISTING_DATABASE": blockers.append("DUPLICATE_EXISTING")
    elif duplicate_status == "DUPLICATE_WITHIN_UPLOAD": blockers.append("DUPLICATE_UPLOAD")
    elif duplicate_status == "POSSIBLE_DUPLICATE": blockers.append("POSSIBLE_DUPLICATE")
    if source_status == "AMBIGUOUS": blockers.append("SOURCE_IDENTITY_AMBIGUOUS")
    if source_status == "IDENTITY_CONFLICT": blockers.append("CLASSIFICATION_REVIEW_REQUIRED")
    if classification.get("special_record"): blockers.append("SPECIAL_RECORD_POLICY_REVIEW")
    elif classification.get("suggested_module") == "BOOKS_CHAPTERS": blockers.append("CLASSIFICATION_REVIEW_REQUIRED")
    elif classification.get("suggested_module") not in {"JOURNAL", "CONFERENCE"}: blockers.append("UNSUPPORTED_MODULE")
    elif classification.get("classification_conflict"): blockers.append("CLASSIFICATION_REVIEW_REQUIRED")
    if date_status not in {"EXACT_BIBTEX", "EXACT_VERIFIED"}: blockers.append("DATE_VERIFICATION_REQUIRED")
    if metadata_status in {"PARSE_ERROR", "UNSUPPORTED", "NEEDS_REVIEW"}: blockers.append("MISSING_REQUIRED_METADATA")
    if unresolved_internal or any(author.get("matching_status") == "SUGGESTED" for author in authors): blockers.append("CONTRIBUTOR_REVIEW_REQUIRED")
    if not faculty: blockers.append("CLAIMANT_REQUIRED")
    if external_or_unmatched: warnings.append("External or unmatched source authors remain; preserve their order during later review.")
    status = blockers[0] if blockers else "READY_FOR_REVIEW"
    return {
        "status": status, "blockers": blockers, "warnings": warnings,
        "explanations": {blocker: {
            "DATE_VERIFICATION_REQUIRED": "A complete publication date is required by the existing save workflow.",
            "CLAIMANT_REQUIRED": "A single claiming Faculty member must be selected during human review.",
            "CONTRIBUTOR_REVIEW_REQUIRED": "One or more potential internal contributors need manual confirmation.",
            "CLASSIFICATION_REVIEW_REQUIRED": "The source classification requires module-specific review.",
            "MISSING_REQUIRED_METADATA": "Required publication metadata is incomplete.",
            "DUPLICATE_EXISTING": "An existing database publication matched this source.",
            "DUPLICATE_UPLOAD": "Another uploaded entry represents this publication.",
            "POSSIBLE_DUPLICATE": "A possible duplicate requires human review.",
            "SOURCE_IDENTITY_AMBIGUOUS": "The CSV source maps to multiple BibTeX entries.",
            "SPECIAL_RECORD_POLICY_REVIEW": "Special document types require policy review.",
            "UNSUPPORTED_MODULE": "The source cannot be assigned to a supported publication module automatically.",
        }.get(blocker, blocker) for blocker in blockers},
        "contributors": {"source_authors": len(authors), "matched_faculty": len(faculty), "matched_students": len(students),
                         "unresolved_internal": len(unresolved_internal), "external_or_unmatched": len(external_or_unmatched)},
        "claimant_candidates": candidates,
    }


def review_dimensions(entries: list[dict]) -> dict:
    """Count independent review dimensions after optional reconciliation."""
    duplicates = Counter(entry.get("duplicate_status") for entry in entries)
    metadata = Counter(entry.get("metadata_status") for entry in entries)
    dates = Counter(entry.get("publication_date_status") for entry in entries)
    classifications = Counter((entry.get("document_classification") or {}).get("suggested_module") for entry in entries)
    comparisons = Counter((entry.get("scopus_match") or {}).get("metadata_comparison") for entry in entries)
    difference_codes = Counter(difference.get("reason_code") for entry in entries for difference in entry.get("source_conflicts", []))
    def readiness_scope(records: list[dict]) -> dict:
        """Summarize entries that have already been classified for review.

        The candidate scope deliberately means *no duplicate detected*, not
        approved for import.  It therefore still includes records blocked by
        date, classification, contributor, or claimant review.
        """
        statuses = Counter((entry.get("import_readiness") or {}).get("status") for entry in records)
        blockers = Counter(blocker for entry in records for blocker in (entry.get("import_readiness") or {}).get("blockers", []))
        return {"total": len(records), "statuses": dict(statuses), "blockers": dict(blockers)}

    all_readiness = readiness_scope(entries)
    potentially_new_entries = [entry for entry in entries if entry.get("duplicate_status") == "NO_DUPLICATE_DETECTED"]
    candidate_readiness = readiness_scope(potentially_new_entries)
    return {
        "duplicate_statuses": dict(duplicates),
        "metadata_statuses": dict(metadata),
        "date_statuses": dict(dates),
        "document_modules": dict(classifications),
        "missing_exact_publication_dates": dates["MISSING"],
        "missing_venues": sum(any(item in {"journal name", "conference venue"} for item in entry.get("missing_metadata", [])) for entry in entries),
        "valid_dois": sum(bool((entry.get("publication") or {}).get("doi")) for entry in entries),
        "missing_dois": sum(not bool((entry.get("publication") or {}).get("doi")) for entry in entries),
        "no_duplicate_detected": duplicates["NO_DUPLICATE_DETECTED"],
        "potentially_new_needs_review": sum(entry.get("duplicate_status") == "NO_DUPLICATE_DETECTED" and entry.get("metadata_status") == "NEEDS_REVIEW" for entry in entries),
        "metadata_comparisons": dict(comparisons),
        "difference_codes": dict(difference_codes),
        "supplementary_metadata": difference_codes["SUPPLEMENTARY_METADATA"],
        "document_type_differences": difference_codes["DOCUMENT_TYPE_DIFFERENCE"],
        # Retain the flat fields for existing analysis clients, and expose
        # explicit scopes for the Stage 1D dashboard.
        "import_readiness": all_readiness["statuses"],
        "readiness_blockers": all_readiness["blockers"],
        "potentially_new": len(potentially_new_entries),
        "readiness_summary": {
            "all_records": all_readiness,
            "potentially_new": candidate_readiness,
        },
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
                "volume": _value(row, "volume"),
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
            differences = _source_differences(candidate, record, method or "TITLE_YEAR")
            identity_conflict = any(item["severity"] == "IDENTITY_CONFLICT" for item in differences)
            result = {**record, "match_method": method, "match_status": "IDENTITY_CONFLICT" if identity_conflict else "MATCHED",
                      "candidate_entry_numbers": candidate_numbers, "source_conflicts": differences,
                      "metadata_comparison": _metadata_comparison(differences), "ambiguity_reason": None}
        csv_results.append(result)
        for index in candidates:
            candidates_by_bib[index].append(result)

    statuses = Counter()
    field_conflicts, severity_conflicts = Counter(), Counter()
    for index, entry in enumerate(entries):
        source_records = candidates_by_bib.get(index, [])
        publication = entry.get("publication") or {}
        unique_records = [record for record in source_records if record["match_status"] in {"MATCHED", "IDENTITY_CONFLICT"}]
        ambiguous_records = [record for record in source_records if record["match_status"] == "AMBIGUOUS"]
        if ambiguous_records or len(unique_records) > 1:
            status, selected, ambiguity_reason = "AMBIGUOUS", None, "MULTIPLE_SOURCE_CANDIDATES" if len(source_records) > 1 else ambiguous_records[0]["ambiguity_reason"]
        elif len(unique_records) == 1:
            selected, ambiguity_reason = unique_records[0], None
            status = selected["match_status"]
        else:
            status, selected, ambiguity_reason = "BIBTEX_ONLY", None, "NO_CSV_CANDIDATE"
        differences = [difference for record in unique_records for difference in record.get("source_conflicts", [])]
        for difference in differences:
            field_conflicts[difference["field"]] += 1
            severity_conflicts[difference["severity"]] += 1
        bib_type = _bibtex_type(entry)
        scopus_type = selected["document_type"] if selected else None
        special = _header(scopus_type or "").upper() in SPECIAL_TYPES
        classification = {
            "bibtex_type": bib_type,
            "scopus_document_type": scopus_type,
            "suggested_module": _document_family(scopus_type) if scopus_type else _bibtex_family(entry),
            "classification_conflict": any(difference["reason_code"] == "DOCUMENT_TYPE_DIFFERENCE" for difference in differences),
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
        readiness = _import_readiness(entry, classification, duplicate_status, status, metadata_status, date_status)
        if duplicate_status == "EXISTING_DATABASE":
            eligibility = "DUPLICATE_REVIEW_EXISTING"
        elif special:
            eligibility = "NOT_ELIGIBLE_CURRENT_PUBLICATION_RULES"
        elif classification["suggested_module"] == "BOOKS_CHAPTERS" or classification["classification_conflict"] or any(difference["severity"] == "IDENTITY_CONFLICT" for difference in differences):
            eligibility = "REQUIRES_DOCUMENT_TYPE_REVIEW"
        elif metadata_status != "COMPLETE":
            eligibility = "REQUIRES_METADATA_COMPLETION"
        else:
            eligibility = "POTENTIALLY_ELIGIBLE_AFTER_REVIEW"
        entry.update({
            "scopus_match": {
                "status": status, "matches": source_records,
                "candidate_entry_numbers": sorted({number for record in source_records for number in record.get("candidate_entry_numbers", [])}),
                "csv_record": selected, "metadata_comparison": _metadata_comparison(differences),
                "matching_evidence": {"method": selected.get("match_method") if selected else None, "candidate_csv_rows": [record["source_row"] for record in source_records], "candidate_scopus_eids": [record["eid"] for record in source_records], "ambiguity_reason": ambiguity_reason},
            },
            "document_classification": classification,
            "duplicate_status": duplicate_status,
            "metadata_status": metadata_status,
            "publication_date_status": date_status,
            "import_eligibility": eligibility,
            "import_readiness": readiness,
            "source_conflicts": differences,
            "conference_suggestions": {
                "proceedings_title": publication.get("proceedings_title") or (publication.get("journal_conference_name") if _bibtex_family(entry) == "CONFERENCE" else None) or (selected.get("source_title") if selected else None),
                "conference_name": publication.get("conference_name") or (selected.get("conference_name") if selected else None),
                "conference_date": selected.get("conference_date") if selected else None,
                "conference_location": publication.get("conference_location") or (selected.get("conference_location") if selected else None),
                "publisher": publication.get("publisher") or (selected.get("publisher") if selected else None),
                "isbn": publication.get("isbn") or (selected.get("isbn") if selected else None),
                "issn": publication.get("issn") or (selected.get("issn") if selected else None),
                "volume": publication.get("volume") or (selected.get("volume") if selected else None),
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
            "unique_csv_matches": csv_statuses["MATCHED"] + csv_statuses["IDENTITY_CONFLICT"],
            "unique_bibtex_matches": statuses["MATCHED"] + statuses["IDENTITY_CONFLICT"],
            "ambiguous_bibtex_entries": statuses["AMBIGUOUS"],
            "bibtex_only_entries": statuses["BIBTEX_ONLY"],
            "csv_only_records": csv_statuses["CSV_ONLY"],
            "ambiguous_csv_records": csv_statuses["AMBIGUOUS"],
            "classification_conflicts": sum(1 for entry in entries if entry.get("document_classification", {}).get("classification_conflict")),
            "identity_conflicts": statuses["IDENTITY_CONFLICT"],
            "entries_with_source_conflicts": sum(bool(entry.get("source_conflicts")) for entry in entries),
            "conflict_fields": dict(field_conflicts),
            "conflict_severities": dict(severity_conflicts),
            "duplicate_csv_eids": sum(count > 1 for count in duplicate_eids.values()),
            "duplicate_csv_dois": sum(count > 1 for count in duplicate_csv_dois.values()),
        },
    }
