from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from urllib.parse import quote

import httpx

from .doi import normalize_doi


class MetadataError(Exception):
    pass


class PublicationMetadataProvider(ABC):
    @abstractmethod
    def fetch_by_doi(self, doi: str) -> dict:
        """Return editable bibliographic metadata without writing a publication."""


def source_date(record, key):
    parts = (record.get(key) or {}).get("date-parts") or []
    # Partial dates are deliberately not invented: the reviewer supplies the day.
    try:
        return date(*parts[0]).isoformat() if len(parts[0]) == 3 else None
    except (IndexError, TypeError, ValueError):
        return None


def parse_crossref(raw: dict, requested_doi: str) -> dict:
    work = raw.get("message")
    if not isinstance(work, dict):
        raise MetadataError("Crossref returned an invalid metadata record")
    def first(key):
        values = work.get(key) or []
        return values[0] if values else None
    online = source_date(work, "published-online")
    printed = source_date(work, "published-print")
    authors = []
    for order, author in enumerate(work.get("author") or [], 1):
        given, family = author.get("given"), author.get("family")
        authors.append({
            "author_order": order,
            "author_name_from_source": author.get("name") or " ".join(filter(None, [given, family])) or f"Author {order}",
            "given_name_from_source": given, "family_name_from_source": family,
            "orcid_from_source": author.get("ORCID"),
            "affiliation_from_source": [a["name"] for a in (author.get("affiliation") or []) if a.get("name")],
            "person_type": "UNKNOWN", "faculty_id": None, "student_id": None,
            "is_internal": False, "is_claiming_faculty": False,
            "is_first_author": order == 1, "is_corresponding_author": False,
            "matching_status": "UNMATCHED", "matching_confidence": None,
        })
    typed_issn = {i.get("type"): i.get("value") for i in work.get("issn-type") or []}
    conference = work.get('type') == 'proceedings-article'
    event = work.get('event') or {}
    return {
        "doi": normalize_doi(work.get("DOI") or requested_doi), "title": first("title") or "",
        "publication_type": {"journal-article": "JOURNAL", "proceedings-article": "CONFERENCE"}.get(work.get("type"), "OTHER"),
        "journal_conference_name": first("container-title"), "publisher": work.get("publisher"),
        "conference_name": event.get('name') if conference else None,
        "proceedings_title": first('container-title') if conference else None,
        "conference_location": event.get('location') if conference else None,
        "conference_start_date": source_date(event, 'start') if conference else None,
        "conference_end_date": source_date(event, 'end') if conference else None,
        "publication_date": source_date(work, "published") or printed or online or source_date(work, "issued"),
        "online_publication_date": online, "print_publication_date": printed,
        "volume": work.get("volume"), "issue": work.get("issue"),
        "pages_or_article_number": work.get("page") or work.get("article-number"),
        "issn": typed_issn.get("print") or (first("ISSN") if not typed_issn else None),
        "eissn": typed_issn.get("electronic"), "isbn": ", ".join(work.get("ISBN") or []) or None,
        "url": work.get("URL"), "metadata_source": "CROSSREF",
        "metadata_fetched_at": datetime.now(timezone.utc).isoformat(), "raw_metadata_json": raw,
        "indexing": [], "authors": authors,
    }


class CrossrefProvider(PublicationMetadataProvider):
    def fetch_by_doi(self, doi: str) -> dict:
        doi = normalize_doi(doi)
        try:
            response = httpx.get(
                f"https://api.crossref.org/works/{quote(doi, safe='')}", timeout=20,
                headers={"User-Agent": "FacultyPublicationManager/1.0", "Accept": "application/json"},
            )
            response.raise_for_status()
            return parse_crossref(response.json(), doi)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise MetadataError("DOI not found in Crossref. Retry or continue with manual entry.") from exc
            raise MetadataError("Crossref is temporarily unavailable. Retry or use manual entry.") from exc
        except (httpx.RequestError, ValueError, TypeError) as exc:
            raise MetadataError("Could not retrieve DOI metadata. Retry or continue manually.") from exc
