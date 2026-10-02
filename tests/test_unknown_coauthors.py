import pytest
from conftest import author, paper, report


@pytest.mark.parametrize("kinds", [["UNKNOWN"], ["EXTERNAL"], ["STUDENT", "UNKNOWN"], []])
def test_faculty_claim_with_optional_unclassified_coauthors(setup, kinds):
    client, _, _ = setup
    payload = paper()
    payload["authors"] = [author(1, "FACULTY", 1, True)]
    for order, kind in enumerate(kinds, 2):
        coauthor = author(order, kind, 1 if kind == "STUDENT" else None)
        coauthor.update(author_name_from_source="Source author", given_name_from_source="Source", family_name_from_source="Author",
                        affiliation_from_source=["Vardhaman College of Engineering"], orcid_from_source="0000-0001-2345-6789")
        payload["authors"].append(coauthor)
    response = client.post("/publications", json=payload)
    assert response.status_code == 201, response.text
    stored = client.get(f"/publications/{response.json()['id']}").json()
    for submitted, actual in zip(payload["authors"], stored["authors"]):
        for field, value in submitted.items():
            assert actual[field] == value
    kpis = report(client, "/publication-kpis").json()
    assert kpis["total"] == kpis["unique_faculty"] == 1
    assert kpis["unique_students"] == int("STUDENT" in kinds)


@pytest.mark.parametrize("kind", ["UNKNOWN", "STUDENT", "EXTERNAL"])
def test_non_faculty_cannot_claim(setup, kind):
    client, _, _ = setup
    payload = paper()
    payload["authors"] = [author(1, kind, 1 if kind == "STUDENT" else None, True)]
    assert client.post("/publications", json=payload).status_code == 422


def test_missing_and_multiple_faculty_claimants_rejected(setup):
    client, _, _ = setup
    payload = paper()
    payload["authors"][0]["is_claiming_faculty"] = False
    assert client.post("/publications", json=payload).status_code == 422
    payload["authors"][0]["is_claiming_faculty"] = True
    payload["authors"][1]["is_claiming_faculty"] = True
    assert client.post("/publications", json=payload).status_code == 422


@pytest.mark.parametrize("kind", ["UNKNOWN", "STUDENT", "EXTERNAL"])
def test_claimable_publication_without_eligible_faculty_is_blocked(setup, kind):
    client, _, _ = setup
    payload = paper()
    payload["authors"] = [author(1, kind, 1 if kind == "STUDENT" else None)]
    assert client.post("/publications", json=payload).status_code == 422
