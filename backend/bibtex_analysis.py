"""Read-only duplicate analysis for uploaded BibTeX files.

This module deliberately builds on :class:`BibTeXPublicationParser`.  It does
not create import rows, database records, evidence files, or master data; its
only output is an in-memory review payload for the Stage 1 upload screen.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .bibtex import BibTeXPublicationParser
from .matching import normalized_name
from .models import Faculty, Publication


PRIMARY_DISPOSITIONS = (
    "PARSE_ERROR",
    "UNSUPPORTED_TYPE",
    "ALREADY_IN_DATABASE",
    "DUPLICATE_WITHIN_FILE",
    "POSSIBLE_DUPLICATE",
    "NEEDS_METADATA_REVIEW",
    "NEW_CANDIDATE",
)


def _venue(values: dict) -> str:
    return values.get("journal_conference_name") or values.get("proceedings_title") or values.get("conference_name") or ""


def _publication_venue(publication: Publication) -> str:
    return publication.journal_conference_name or publication.proceedings_title or publication.conference_name or ""


def _year(publication: Publication) -> str:
    return str(publication.publication_date.year) if publication.publication_date else ""


def _title_year_venue(title: str, year: str, venue: str) -> tuple[str, str, str] | None:
    normalized = (normalized_name(title), str(year or "").strip(), normalized_name(venue))
    return normalized if all(normalized) else None


def _possible_match(left: dict, right: dict) -> bool:
    """A deliberately conservative title/year/venue candidate check.

    It never labels a fuzzy title as an exact duplicate.  The same year and a
    non-empty comparable venue are required, which keeps common short titles
    out of the possible-duplicate bucket.
    """
    if not left["title"] or not right["title"] or left["year"] != right["year"] or not left["year"]:
        return False
    if not left["venue"] or not right["venue"]:
        return False
    title_ratio = SequenceMatcher(None, left["title"], right["title"]).ratio()
    venue_ratio = SequenceMatcher(None, left["venue"], right["venue"]).ratio()
    return title_ratio >= 0.92 and venue_ratio >= 0.70 and (title_ratio < 1 or venue_ratio < 1)


def _database_reference(publication: Publication, faculty_names: dict[int, str]) -> dict:
    claimant = next((author for author in publication.authors if author.is_claiming_faculty and author.faculty_id), None)
    return {
        "publication_id": publication.id,
        "title": publication.title,
        "publication_type": publication.publication_type,
        "doi": publication.doi,
        "is_active": publication.is_active,
        "claiming_faculty": None if claimant is None else {
            "faculty_id": claimant.faculty_id,
            "name": faculty_names.get(claimant.faculty_id, claimant.author_name_from_source),
        },
    }


def analyze_bibtex(content: str, db: Session, provider) -> dict:
    """Parse and classify a BibTeX upload without changing application data."""
    parsed = BibTeXPublicationParser().parse(content, db, provider, enrich=False)
    entries = parsed["entries"]
    publications = list(db.scalars(select(Publication).options(selectinload(Publication.authors))))
    faculty_names = dict(db.execute(select(Faculty.id, Faculty.name)).all())

    database_by_doi: dict[str, list[Publication]] = defaultdict(list)
    database_by_key: dict[tuple[str, str, str], list[Publication]] = defaultdict(list)
    database_candidates: list[tuple[dict, Publication]] = []
    for existing in publications:
        if existing.doi:
            database_by_doi[existing.doi].append(existing)
        key = _title_year_venue(existing.title, _year(existing), _publication_venue(existing))
        if key:
            database_by_key[key].append(existing)
        database_candidates.append(({
            "title": normalized_name(existing.title),
            "year": _year(existing),
            "venue": normalized_name(_publication_venue(existing)),
        }, existing))

    normalized_entries: list[dict | None] = []
    doi_groups: dict[str, list[int]] = defaultdict(list)
    key_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    citation_groups: dict[str, list[int]] = defaultdict(list)
    for index, entry in enumerate(entries):
        draft = entry.get("publication") or {}
        values = {
            "title": normalized_name(draft.get("title")),
            "year": str(entry.get("publication_year") or "").strip(),
            "venue": normalized_name(_venue(draft)),
            "doi": draft.get("doi") or "",
        }
        normalized_entries.append(values if draft else None)
        if values["doi"]:
            doi_groups[values["doi"]].append(index)
        key = _title_year_venue(draft.get("title", ""), values["year"], _venue(draft))
        if key:
            key_groups[key].append(index)
        if entry.get("citation_key"):
            citation_groups[str(entry["citation_key"])].append(index)

    for index, entry in enumerate(entries):
        draft = entry.get("publication") or {}
        values = normalized_entries[index]
        exact_database: list[dict] = []
        exact_file: list[dict] = []
        possible_database: list[dict] = []
        possible_file: list[dict] = []
        repeated_keys: list[dict] = []

        if values:
            if values["doi"]:
                exact_database.extend(_database_reference(publication, faculty_names) for publication in database_by_doi[values["doi"]])
                exact_file.extend({"entry_number": entries[other]["entry_number"], "citation_key": entries[other].get("citation_key"), "reason": "Repeated normalized DOI"}
                                  for other in doi_groups[values["doi"]] if other != index)
            key = _title_year_venue(draft.get("title", ""), values["year"], _venue(draft))
            if key:
                exact_database.extend(_database_reference(publication, faculty_names) for publication in database_by_key[key] if publication.id not in {item["publication_id"] for item in exact_database})
                exact_file.extend({"entry_number": entries[other]["entry_number"], "citation_key": entries[other].get("citation_key"), "reason": "Same normalized title, year and venue"}
                                  for other in key_groups[key] if other != index and not any(match["entry_number"] == entries[other]["entry_number"] for match in exact_file))
            for candidate, publication in database_candidates:
                if publication.id not in {item["publication_id"] for item in exact_database} and _possible_match(values, candidate):
                    possible_database.append(_database_reference(publication, faculty_names))
            for other, candidate in enumerate(normalized_entries):
                if other != index and candidate and not any(match["entry_number"] == entries[other]["entry_number"] for match in exact_file) and _possible_match(values, candidate):
                    possible_file.append({"entry_number": entries[other]["entry_number"], "citation_key": entries[other].get("citation_key"), "reason": "Similar title, year and venue"})
            if entry.get("citation_key"):
                repeated_keys = [{"entry_number": entries[other]["entry_number"], "citation_key": entries[other].get("citation_key")}
                                 for other in citation_groups[str(entry["citation_key"])] if other != index]

        missing = []
        if draft:
            for field, value in (("title", draft.get("title")), ("publication year", entry.get("publication_year"))):
                if not value:
                    missing.append(field)
            if draft.get("publication_type") == "JOURNAL" and not draft.get("journal_conference_name"):
                missing.append("journal name")
            elif draft.get("publication_type") == "CONFERENCE" and not _venue(draft):
                # The current input schema accepts a proceedings title or a
                # conference name.  Analysis must not falsely require both.
                missing.append("conference venue")
            if not draft.get("publication_date"):
                missing.append("exact publication date")
        if entry.get("errors"):
            disposition = "PARSE_ERROR"
        elif draft.get("publication_type") == "OTHER":
            disposition = "UNSUPPORTED_TYPE"
        elif exact_database:
            disposition = "ALREADY_IN_DATABASE"
        elif exact_file:
            disposition = "DUPLICATE_WITHIN_FILE"
        elif possible_database or possible_file:
            disposition = "POSSIBLE_DUPLICATE"
        elif missing or any(author.get("matching_status") == "SUGGESTED" for author in draft.get("authors", [])):
            disposition = "NEEDS_METADATA_REVIEW"
        else:
            disposition = "NEW_CANDIDATE"

        entry.update({
            "primary_disposition": disposition,
            "duplicate_matches": {"database_exact": exact_database, "within_file_exact": exact_file,
                                  "database_possible": possible_database, "within_file_possible": possible_file},
            "missing_metadata": missing,
            "repeated_citation_keys": repeated_keys,
            "analysis_warnings": (["Citation key is repeated in this upload; citation keys are not treated as global identifiers."] if repeated_keys else []),
        })

    disposition_counts = Counter(entry["primary_disposition"] for entry in entries)
    # These dimensions intentionally do not replace the mutually-exclusive
    # primary disposition above.  They give a reviewer separate answers to
    # "is it a duplicate?", "is its metadata usable?", and "what kind of
    # document is it?" even when no Scopus CSV was supplied.
    from .scopus_analysis import reconcile_scopus_entries, review_dimensions
    reconcile_scopus_entries(entries, [])
    return {
        "analysis_only": True,
        "total_entries": len(entries),
        "entries": entries,
        "summary": {
            "total_entries": len(entries),
            "successfully_parsed": sum(bool(entry.get("publication")) and not entry.get("errors") for entry in entries),
            "parse_errors": disposition_counts["PARSE_ERROR"],
            "unsupported_types": disposition_counts["UNSUPPORTED_TYPE"],
            "exact_duplicates_within_file": disposition_counts["DUPLICATE_WITHIN_FILE"],
            "possible_duplicates_within_file": sum(bool(entry["duplicate_matches"]["within_file_possible"]) for entry in entries),
            "exact_matches_already_in_database": disposition_counts["ALREADY_IN_DATABASE"],
            "possible_matches_in_database": sum(bool(entry["duplicate_matches"]["database_possible"]) for entry in entries),
            "new_candidates": disposition_counts["NEW_CANDIDATE"],
            "needs_metadata_review": disposition_counts["NEEDS_METADATA_REVIEW"],
            "primary_dispositions": {key: disposition_counts[key] for key in PRIMARY_DISPOSITIONS},
            "review_dimensions": review_dimensions(entries),
        },
    }
