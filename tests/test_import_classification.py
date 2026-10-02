import pytest
from conftest import author, paper, report


@pytest.mark.parametrize("kind", ["JOURNAL", "CONFERENCE"])
@pytest.mark.parametrize("classification", ["INTERNATIONAL", "NATIONAL", "OTHER", "UNKNOWN"])
def test_classification_independent_of_overlapping_indexing(setup, kind, classification):
    client, _, _ = setup
    payload = paper()
    payload.update(publication_type=kind, classification=classification, indexing=["SCIE", "SCOPUS", "WEB_OF_SCIENCE"], quartile="NOT_APPLICABLE", impact_factor=None)
    payload["authors"].append(author(5, "UNKNOWN"))
    response = client.post("/publications", json=payload)
    assert response.status_code == 201, response.text
    stored = response.json()
    assert stored["indexing"] == payload["indexing"]
    assert stored["classification"] == classification
    assert stored["impact_factor"] is None
    assert stored["quartile"] == "NOT_APPLICABLE"
    kpis = report(client, "/publication-kpis").json()
    assert kpis["total"] == kpis["scie"] == kpis["scopus"] == kpis["web_of_science"] == 1
    if classification in {"INTERNATIONAL", "NATIONAL"}:
        metric = f"{classification.lower()}_{kind.lower()}"
        assert kpis[metric] == 1
        assert len(report(client, f"/publications?metric={metric}").json()) == 1
    assert report(client, "/publication-kpis", "2026-10-01", "2026-10-31").json()["total"] == 0


def test_classification_filter_and_old_client_edit_preservation(setup):
    client, _, _ = setup
    payload = paper()
    payload["classification"] = "INTERNATIONAL"
    identity = client.post("/publications", json=payload).json()["id"]
    assert len(report(client, "/publications?classification=INTERNATIONAL").json()) == 1
    assert report(client, "/publications?classification=NATIONAL").json() == []
    payload.pop("classification")
    assert client.put(f"/publications/{identity}", json=payload).json()["classification"] == "INTERNATIONAL"
    faculty = report(client, "/publication-kpis/faculty").json()
    assert faculty[0]["international"] == 1
    assert faculty[0]["scopus"] == 1


def test_invalid_classification_rejected(setup):
    client, _, _ = setup
    payload = paper()
    payload["classification"] = "IEEE"
    assert client.post("/publications", json=payload).status_code == 422
