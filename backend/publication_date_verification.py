"""Read-only, bounded publication-date evidence retrieval.

This module deliberately returns evidence only.  It does not know about the
publication save path, ORM session, evidence storage, or claimant assignment.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from time import sleep
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse

import httpx

from .doi import normalize_doi
from .matching import normalized_name
from .metadata import MetadataError, crossref_date_candidates


class DateVerificationError(Exception):
    pass


USER_AGENT = "FacultyResearchDevelopmentPortal/1.0 (analysis-only date verification)"
MAX_REDIRECTS = 3
MAX_HTML_BYTES = 1_000_000
ALLOWED_API_HOSTS = {"api.datacite.org", "api.openalex.org", "api.crossref.org", "doi.org", "dx.doi.org"}


def _precision_date(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", value.strip())
    if not match:
        return None
    year, month, day = match.groups()
    if day:
        try:
            return datetime(int(year), int(month), int(day)).date().isoformat(), "DAY"
        except ValueError:
            return None
    if month and 1 <= int(month) <= 12:
        return f"{year}-{int(month):02d}", "MONTH"
    return year, "YEAR"


def _candidate(value: str | None, date_type: str, source: str, source_field: str, source_url: str, assessment: str) -> dict | None:
    parsed = _precision_date(value)
    if not parsed:
        return None
    date_value, precision = parsed
    return {"date": date_value, "precision": precision, "date_type": date_type, "source": source,
            "source_field": source_field, "source_url": source_url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "assessment": assessment}


def _crossref_candidates(raw: dict, doi: str) -> tuple[list[dict], str | None]:
    message = raw.get("message") if isinstance(raw, dict) else None
    if not isinstance(message, dict):
        return [], None
    source_url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    label_map = {"ONLINE": ("ONLINE_PUBLICATION", "EXACT_ONLINE"), "PUBLISHED": ("PUBLICATION_DATE", "EXACT_PUBLICATION"),
                 "PRINT": ("PRINT_PUBLICATION", "PRINT_ONLY"), "ISSUED": ("PUBLICATION_DATE", "PUBLICATION_DATE")}
    result = []
    for item in crossref_date_candidates(raw)["alternatives"]:
        date_type, assessment = label_map[item["date_type"]]
        result.append({**item, "date_type": date_type, "source": "CROSSREF", "source_url": source_url,
                       "retrieved_at": datetime.now(timezone.utc).isoformat(), "assessment": assessment})
    title = (message.get("title") or [None])[0]
    return result, title


class _StructuredMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self._json_ld = False
        self._script = []
        self.json_ld: list[object] = []

    def handle_starttag(self, tag, attrs):
        values = {key.casefold(): value for key, value in attrs}
        if tag.casefold() == "meta":
            key = (values.get("name") or values.get("property") or values.get("itemprop") or "").casefold()
            value = values.get("content")
            if key and value:
                self.meta.setdefault(key, []).append(value.strip())
        if tag.casefold() == "script" and (values.get("type") or "").casefold() == "application/ld+json":
            self._json_ld, self._script = True, []

    def handle_data(self, data):
        if self._json_ld:
            self._script.append(data)

    def handle_endtag(self, tag):
        if tag.casefold() == "script" and self._json_ld:
            self._json_ld = False
            try:
                self.json_ld.append(json.loads("".join(self._script)))
            except json.JSONDecodeError:
                pass


def _json_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from _json_objects(item)
    elif isinstance(value, dict):
        yield value
        if "@graph" in value:
            yield from _json_objects(value["@graph"])


class PublicationDateVerifier:
    """Sequential verifier with guarded web retrieval and deterministic parsing."""

    def __init__(self, crossref_provider, client: httpx.Client | None = None, resolver=None):
        self.crossref_provider = crossref_provider
        self.client = client or httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=False,
                                             headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9"})
        self.resolver = resolver or socket.getaddrinfo

    def close(self):
        self.client.close()

    @staticmethod
    def _retry(lookup):
        for attempt in range(2):
            try:
                return lookup()
            except httpx.HTTPStatusError as exc:
                if attempt or exc.response.status_code not in {429, 500, 502, 503, 504}:
                    raise
                sleep(0.2)
            except httpx.RequestError:
                if attempt:
                    raise
                sleep(0.2)

    def _validate_url(self, url: str, *, publisher: bool = False) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise DateVerificationError("Only HTTPS public metadata URLs are permitted.")
        host = parsed.hostname.casefold().rstrip(".")
        if not publisher and host not in ALLOWED_API_HOSTS:
            raise DateVerificationError("The metadata endpoint is not approved.")
        try:
            addresses = self.resolver(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise DateVerificationError("The metadata host could not be resolved safely.") from exc
        for _, _, _, _, sockaddr in addresses:
            candidate = ipaddress.ip_address(sockaddr[0])
            if not candidate.is_global:
                raise DateVerificationError("Private or internal metadata targets are not permitted.")
        return url

    def _request(self, url: str, *, accept: str, publisher: bool = False) -> httpx.Response:
        current = self._validate_url(url, publisher=publisher)
        robots_checked = set()
        for _ in range(MAX_REDIRECTS + 1):
            host = urlparse(current).hostname.casefold().rstrip(".")
            if publisher and host not in {"doi.org", "dx.doi.org"} and host not in robots_checked:
                self._check_robots(current)
                robots_checked.add(host)
            response = self.client.get(current, headers={"Accept": accept, "User-Agent": USER_AGENT})
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response
            location = response.headers.get("location")
            if not location:
                raise DateVerificationError("Metadata redirect did not provide a target.")
            current = self._validate_url(urljoin(current, location), publisher=True)
            publisher = True
        raise DateVerificationError("Metadata redirect limit exceeded.")

    def _check_robots(self, article_url: str):
        """Respect an explicit robots disallow rule; unavailable robots is not bypassed."""
        parsed = urlparse(article_url)
        robots_url = self._validate_url(f"https://{parsed.hostname}/robots.txt", publisher=True)
        try:
            response = self.client.get(robots_url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
        except httpx.RequestError as exc:
            raise DateVerificationError("Publisher robots policy could not be retrieved safely.") from exc
        if response.status_code != 200 or len(response.content) > 200_000:
            return
        applies, disallowed = False, []
        for raw_line in response.text.splitlines():
            key, _, value = raw_line.partition(":")
            key, value = key.strip().casefold(), value.strip()
            if key == "user-agent":
                applies = value in {"*", USER_AGENT.casefold()}
            elif applies and key == "disallow" and value:
                disallowed.append(value)
        if any(parsed.path.startswith(path) for path in disallowed):
            raise DateVerificationError("Publisher robots policy disallows automated article metadata retrieval.")

    def _datacite(self, doi: str) -> tuple[list[dict], str | None, str | None]:
        url = f"https://api.datacite.org/dois/{quote(doi, safe='')}"
        response = self._request(url, accept="application/vnd.api+json")
        if response.status_code == 404:
            return [], None, "DataCite has no record for this DOI."
        response.raise_for_status()
        attributes = ((response.json().get("data") or {}).get("attributes") or {})
        candidates = []
        for item in attributes.get("dates") or []:
            kind = str(item.get("dateType") or "").casefold()
            if kind not in {"issued", "published", "available"}:
                continue
            candidates.append(_candidate(item.get("date"), "PUBLICATION_DATE", "DATACITE", f"dates.{kind}", url, "PUBLICATION_DATE"))
        candidates = [item for item in candidates if item]
        if not candidates:
            year = attributes.get("publicationYear")
            candidates = [_candidate(str(year) if year else None, "PUBLICATION_YEAR", "DATACITE", "publicationYear", url, "YEAR_ONLY")]
            candidates = [item for item in candidates if item]
        titles = attributes.get("titles") or []
        return candidates, (titles[0].get("title") if titles else None), None

    def _openalex(self, doi: str) -> tuple[list[dict], str | None, str | None]:
        url = f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='')}"
        response = self._request(url, accept="application/json")
        if response.status_code == 404:
            return [], None, "OpenAlex has no record for this DOI."
        response.raise_for_status()
        data = response.json()
        candidate = _candidate(data.get("publication_date") or str(data.get("publication_year") or ""),
                               "AGGREGATOR_PUBLICATION_DATE", "OPENALEX", "publication_date", url, "AGGREGATOR_DATE")
        return ([candidate] if candidate else []), data.get("display_name"), None

    def _publisher(self, doi: str) -> tuple[list[dict], str | None, str | None]:
        resolver_url = f"https://doi.org/{quote(doi, safe='')}"
        response = self._request(resolver_url, accept="text/html", publisher=False)
        if response.status_code >= 400:
            return [], None, f"Publisher landing page returned HTTP {response.status_code}."
        content_type = response.headers.get("content-type", "").casefold()
        if "text/html" not in content_type:
            return [], None, "Publisher landing page did not return HTML."
        payload = response.content
        if len(payload) > MAX_HTML_BYTES:
            return [], None, "Publisher landing page exceeds the analysis size limit."
        parser = _StructuredMetadataParser()
        parser.feed(payload.decode(response.encoding or "utf-8", errors="replace"))
        candidates, title = [], None
        fields = [("citation_first_online_date", "FIRST_ONLINE_PUBLICATION", "EXACT_FIRST_ONLINE"), ("citation_online_date", "ONLINE_PUBLICATION", "EXACT_ONLINE"), ("citation_publication_date", "PUBLICATION_DATE", "EXACT_PUBLICATION"),
                  ("citation_date", "PUBLICATION_DATE", "EXACT_PUBLICATION"), ("dc.date", "PUBLICATION_DATE", "EXACT_PUBLICATION"),
                  ("dcterms.date", "PUBLICATION_DATE", "EXACT_PUBLICATION")]
        for field, kind, assessment in fields:
            for value in parser.meta.get(field, []):
                candidate = _candidate(value, kind, "PUBLISHER", field, str(response.url), assessment)
                if candidate:
                    candidates.append(candidate)
        title = next(iter(parser.meta.get("citation_title", [])), None)
        for data in parser.json_ld:
            for item in _json_objects(data):
                if not title:
                    title = item.get("headline") or item.get("name")
                candidate = _candidate(item.get("datePublished"), "PUBLICATION_DATE", "PUBLISHER", "json-ld.datePublished", str(response.url), "EXACT_PUBLICATION")
                if candidate:
                    candidates.append(candidate)
        return candidates, title, None

    @staticmethod
    def _identity_status(upload_title: str | None, source_titles: list[str | None]) -> str:
        target = normalized_name(upload_title)
        values = [normalized_name(value) for value in source_titles if value]
        if not target or not values:
            return "INSUFFICIENT_EVIDENCE"
        ratios = [__import__("difflib").SequenceMatcher(None, target, value).ratio() for value in values]
        if any(value == target for value in values):
            return "VERIFIED_IDENTITY"
        if any(ratio >= 0.86 for ratio in ratios):
            return "LIKELY_IDENTITY"
        return "IDENTITY_CONFLICT"

    @staticmethod
    def _select(candidates: list[dict], identity_status: str) -> tuple[dict | None, str, bool]:
        if identity_status == "IDENTITY_CONFLICT":
            return None, "IDENTITY_CONFLICT", True
        if not candidates:
            return None, "NO_RELIABLE_DATE", True
        unique_exact_days = {candidate["date"] for candidate in candidates if candidate["precision"] == "DAY" and candidate["date_type"] in {"FIRST_ONLINE_PUBLICATION", "ONLINE_PUBLICATION", "PUBLICATION_DATE", "PRINT_PUBLICATION"}}
        if len(unique_exact_days) > 1:
            return None, "CONFLICTING_DATES", True
        priority = {"FIRST_ONLINE_PUBLICATION": 0, "ONLINE_PUBLICATION": 1, "PUBLICATION_DATE": 2, "PRINT_PUBLICATION": 3, "AGGREGATOR_PUBLICATION_DATE": 4, "PUBLICATION_YEAR": 5}
        preferred = sorted(candidates, key=lambda item: (priority.get(item["date_type"], 9), {"DAY": 0, "MONTH": 1, "YEAR": 2}[item["precision"]]))[0]
        if preferred["date_type"] == "FIRST_ONLINE_PUBLICATION" and preferred["precision"] == "DAY":
            return preferred, "EXACT_FIRST_ONLINE_FOUND", identity_status != "VERIFIED_IDENTITY"
        if preferred["date_type"] == "ONLINE_PUBLICATION" and preferred["precision"] == "DAY":
            return preferred, "EXACT_ONLINE_FOUND", identity_status != "VERIFIED_IDENTITY"
        if preferred["date_type"] in {"PUBLICATION_DATE", "AGGREGATOR_PUBLICATION_DATE"} and preferred["precision"] == "DAY":
            return preferred, "EXACT_PUBLICATION_DATE_FOUND", True
        if preferred["date_type"] == "PRINT_PUBLICATION" and preferred["precision"] == "DAY":
            return preferred, "PRINT_ONLY_FOUND", True
        if preferred["precision"] in {"MONTH", "YEAR"}:
            return preferred, "PARTIAL_DATE_FOUND" if preferred["precision"] == "MONTH" else "YEAR_ONLY_FOUND", True
        return preferred, "NO_RELIABLE_DATE", True

    def verify(self, doi: str, *, title: str | None = None, publication_year: str | None = None, bibtex_date: str | None = None) -> dict:
        doi = normalize_doi(doi)
        candidates, failures, titles = [], [], []
        try:
            crossref = None
            crossref_failure = None
            for attempt in range(2):
                try:
                    crossref = self.crossref_provider.fetch_by_doi(doi)
                    break
                except MetadataError as exc:
                    crossref_failure = exc
                    if attempt or "not found" in str(exc).casefold():
                        break
                    sleep(0.2)
            if crossref is None:
                raise crossref_failure or MetadataError("Crossref metadata is unavailable.")
            found, source_title = _crossref_candidates(crossref.get("raw_metadata_json") or {}, doi)
            candidates.extend(found); titles.append(source_title)
        except MetadataError as exc:
            failures.append({"source": "CROSSREF", "error": str(exc)})
        # Query other sources only when Crossref did not deliver an exact online day.
        if not any(item["source"] == "CROSSREF" and item["date_type"] == "ONLINE_PUBLICATION" and item["precision"] == "DAY" for item in candidates):
            for name, lookup in (("DATACITE", self._datacite), ("OPENALEX", self._openalex), ("PUBLISHER", self._publisher)):
                try:
                    found, source_title, note = self._retry(lambda lookup=lookup: lookup(doi))
                    candidates.extend(found); titles.append(source_title)
                    if note:
                        failures.append({"source": name, "error": note})
                except (httpx.HTTPError, DateVerificationError, ValueError) as exc:
                    failures.append({"source": name, "error": str(exc)})
        identity_status = self._identity_status(title, titles)
        suggested, status, requires_review = self._select(candidates, identity_status)
        bibtex_date_conflict = bool(bibtex_date and suggested and bibtex_date != suggested["date"])
        return {"doi": doi, "identity_status": identity_status, "candidates": candidates, "suggested_date": suggested,
                "suggestion_status": status, "requires_review": requires_review, "provider_failures": failures,
                "bibtex_date_conflict": bibtex_date_conflict, "uploaded_year": publication_year or None}
