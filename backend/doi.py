import re
from urllib.parse import unquote


def normalize_doi(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I)
    doi = unquote(doi).strip().lower()
    if not re.fullmatch(r"10\.\d{4,9}/[^\s]+", doi):
        raise ValueError("Enter a valid DOI, for example 10.1234/example.123")
    return doi


def normalize_orcid(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    value = re.sub(r"^https?://orcid.org/", "", value.strip(), flags=re.I).upper()
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", value):
        raise ValueError("ORCID must be xxxx-xxxx-xxxx-xxxx or an orcid.org URL")
    return value


def parse_doi_input(content: str) -> list[dict]:
    """Split pasted identifiers and deduplicate using the same keys as SQLite saves."""
    entries, seen = [], set()
    # Spaces delimit identifiers only when another DOI prefix is identifiable.
    # Keep the optional whitespace following `doi:` attached to its identifier.
    content = re.sub(r"\b(doi:)[ \t]+", r"\1", content, flags=re.I)
    for source in re.split(r"[,;\r\n]+|\s+(?=(?:https?://(?:dx\.)?doi\.org/|doi:|10\.\d{4,9}/))", content, flags=re.I):
        source = source.strip()
        if not source:
            continue
        try:
            doi = normalize_doi(source)
            key = ("DOI", doi)
            entry = {"source": source, "doi": doi, "status": "PENDING"}
        except ValueError as exc:
            key = ("INVALID", source.casefold())
            entry = {"source": source, "doi": None, "status": "INVALID_DOI", "error": str(exc)}
        if key not in seen:
            seen.add(key)
            entries.append(entry)
    return entries

