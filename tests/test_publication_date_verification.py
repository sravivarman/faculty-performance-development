import socket

import httpx
import pytest

from backend.metadata import MetadataError
from backend.publication_date_verification import DateVerificationError, PublicationDateVerifier


PUBLIC_ADDRESS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]


class Provider:
    def __init__(self, raw=None, error=None):
        self.raw, self.error = raw, error

    def fetch_by_doi(self, _doi):
        if self.error:
            raise self.error
        return {"raw_metadata_json": self.raw}


class Client:
    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        for prefix, response in self.routes.items():
            if url.startswith(prefix):
                if callable(response):
                    return response(url)
                return response
        return response_for(url, 404, {})

    def close(self):
        pass


def response_for(url, status, payload=None, *, headers=None, content=None):
    options = {"headers": headers or {}, "request": httpx.Request("GET", url)}
    if content is not None:
        return httpx.Response(status, content=content, **options)
    return httpx.Response(status, json=payload, **options)


def verifier(raw=None, *, error=None, routes=None, resolver=lambda *_args, **_kwargs: PUBLIC_ADDRESS):
    return PublicationDateVerifier(Provider(raw, error), client=Client(routes or {}), resolver=resolver)


def test_crossref_exact_online_date_is_preferred_with_provenance():
    check = verifier({"message": {"title": ["Power converter"], "published-online": {"date-parts": [[2025, 3, 15]]}, "created": {"date-parts": [[2024, 1, 1]]}}})
    result = check.verify("10.1234/date", title="Power converter", publication_year="2025")
    assert result["identity_status"] == "VERIFIED_IDENTITY"
    assert result["suggestion_status"] == "EXACT_ONLINE_FOUND"
    assert result["suggested_date"]["date"] == "2025-03-15"
    assert result["suggested_date"]["source"] == "CROSSREF"
    assert all(candidate["source_field"] not in {"created", "deposited"} for candidate in result["candidates"])


def test_datacite_partial_date_is_preserved_when_crossref_has_no_publication_evidence():
    routes = {
        "https://api.datacite.org/": response_for("https://api.datacite.org/dois/10.1234/date", 200, {"data": {"attributes": {"titles": [{"title": "Partial record"}], "dates": [{"date": "2025-06", "dateType": "Issued"}]}}}),
        "https://api.openalex.org/": response_for("https://api.openalex.org/works/x", 404, {}),
        "https://doi.org/": response_for("https://doi.org/10.1234/date", 404, {}),
    }
    check = verifier({"message": {"title": ["Partial record"], "created": {"date-parts": [[2025, 1, 1]]}}}, routes=routes)
    result = check.verify("10.1234/date", title="Partial record")
    assert result["suggestion_status"] == "PARTIAL_DATE_FOUND"
    assert result["suggested_date"]["date"] == "2025-06"
    assert result["suggested_date"]["precision"] == "MONTH"
    assert result["suggested_date"]["source"] == "DATACITE"


def test_publisher_structured_metadata_is_used_only_after_crossref_lacks_exact_online_date():
    html = b'<html><head><meta name="citation_title" content="Publisher record"><meta name="citation_online_date" content="2025-04-01"></head></html>'
    routes = {
        "https://api.datacite.org/": response_for("https://api.datacite.org/dois/10.1234/publisher", 404, {}),
        "https://api.openalex.org/": response_for("https://api.openalex.org/works/x", 404, {}),
        "https://doi.org/": response_for("https://doi.org/10.1234/publisher", 200, headers={"content-type": "text/html; charset=utf-8"}, content=html),
    }
    check = verifier({"message": {"title": ["Publisher record"], "issued": {"date-parts": [[2025]]}}}, routes=routes)
    result = check.verify("10.1234/publisher", title="Publisher record")
    assert result["suggestion_status"] == "EXACT_ONLINE_FOUND"
    assert result["suggested_date"]["source"] == "PUBLISHER"
    assert result["suggested_date"]["date"] == "2025-04-01"


def test_title_identity_conflict_never_suggests_crossref_date():
    check = verifier({"message": {"title": ["Correction to another article"], "published-online": {"date-parts": [[2025, 3, 15]]}}})
    result = check.verify("10.1234/correction", title="Unrelated original article")
    assert result["identity_status"] == "IDENTITY_CONFLICT"
    assert result["suggestion_status"] == "IDENTITY_CONFLICT"
    assert result["suggested_date"] is None


def test_publisher_fetch_rejects_private_targets_and_redirect_loops():
    private = verifier(resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(DateVerificationError, match="Private or internal"):
        private._validate_url("https://publisher.example/article", publisher=True)
    loop = verifier(routes={"https://doi.org/": lambda url: response_for(url, 302, headers={"location": url})})
    with pytest.raises(DateVerificationError, match="redirect limit"):
        loop._publisher("10.1234/loop")


def test_publisher_fetch_respects_explicit_robots_disallow():
    def publisher_response(url):
        if url.endswith("/robots.txt"):
            return response_for(url, 200, headers={"content-type": "text/plain"}, content=b"User-agent: *\nDisallow: /article")
        return response_for(url, 200, headers={"content-type": "text/html"}, content=b"<html></html>")

    check = verifier(routes={
        "https://doi.org/": lambda url: response_for(url, 302, headers={"location": "https://publisher.example/article"}),
        "https://publisher.example/": publisher_response,
    })
    with pytest.raises(DateVerificationError, match="robots policy"):
        check._publisher("10.1234/robots")


def test_crossref_failure_can_use_openalex_fallback_without_writing():
    routes = {
        "https://api.datacite.org/": response_for("https://api.datacite.org/dois/10.1234/openalex", 404, {}),
        "https://api.openalex.org/": response_for("https://api.openalex.org/works/x", 200, {"display_name": "OpenAlex work", "publication_date": "2025-07-12"}),
        "https://doi.org/": response_for("https://doi.org/10.1234/openalex", 404, {}),
    }
    check = verifier(error=MetadataError("DOI not found in Crossref."), routes=routes)
    result = check.verify("10.1234/openalex", title="OpenAlex work")
    assert any(candidate["source"] == "OPENALEX" for candidate in result["candidates"])
    assert result["suggested_date"] is not None


def test_no_reliable_date_reports_completed_provider_outcome():
    routes = {
        "https://api.datacite.org/": response_for("https://api.datacite.org/dois/10.1234/missing", 404, {}),
        "https://api.openalex.org/": response_for("https://api.openalex.org/works/x", 404, {}),
        "https://doi.org/": response_for("https://doi.org/10.1234/missing", 404, {}),
    }
    check = verifier({"message": {"title": ["No date record"]}}, routes=routes)
    result = check.verify("10.1234/missing", title="No date record")
    assert result["suggestion_status"] == "NO_RELIABLE_DATE"
    assert result["suggested_date"] is None
    assert {failure["source"] for failure in result["provider_failures"]} == {"DATACITE", "OPENALEX", "PUBLISHER"}


def test_timeout_and_http_failure_are_returned_as_provider_diagnostics():
    def timeout(_url):
        raise httpx.ReadTimeout("provider timed out", request=httpx.Request("GET", "https://api.datacite.org/dois/10.1234/failure"))

    routes = {
        "https://api.datacite.org/": timeout,
        "https://api.openalex.org/": response_for("https://api.openalex.org/works/x", 503, {}),
        "https://doi.org/": response_for("https://doi.org/10.1234/failure", 500, {}),
    }
    check = verifier({"message": {"title": ["Failure record"]}}, routes=routes)
    result = check.verify("10.1234/failure", title="Failure record")
    failures = {item["source"]: item["error"] for item in result["provider_failures"]}
    assert result["suggestion_status"] == "NO_RELIABLE_DATE"
    assert "DATACITE" in failures and "timed out" in failures["DATACITE"]
    assert "OPENALEX" in failures and "503" in failures["OPENALEX"]
    assert "PUBLISHER" in failures and "500" in failures["PUBLISHER"]
