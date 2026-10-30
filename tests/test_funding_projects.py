from decimal import Decimal


def funding(category="SPONSORED_RESEARCH", status="DRAFT", **changes):
    value = {
        "title": f"{category} project",
        "category": category,
        "department": "CSE",
        "funding_agency": "Research Council",
        "proposal_submission_date": "2026-08-01",
        "sanction_date": None,
        "start_date": None,
        "end_date": None,
        "sanctioned_amount": None,
        "amount_received": None,
        "amount_utilized": None,
        "reference_number": None,
        "status": status,
        "faculty": [{"faculty_id": 1, "role": "PI"}, {"faculty_id": 2, "role": "CO_PI"}],
    }
    if status in ("SANCTIONED", "ONGOING", "COMPLETED"):
        value.update({"sanction_date": "2026-08-10", "start_date": "2026-08-15", "sanctioned_amount": "125000.50"})
    value.update(changes)
    return value


def test_funding_categories_associations_and_validation(setup):
    client, _, _ = setup
    sponsored = client.post("/funding-projects", json=funding("SPONSORED_RESEARCH", "SANCTIONED"))
    consultancy = client.post("/funding-projects", json=funding("CONSULTANCY", "ONGOING", title="Industry study", amount_received="50000.25"))
    internal = client.post("/funding-projects", json=funding("INTERNAL_GRANT", "COMPLETED", title="Seed support", amount_utilized="0.00", faculty=[{"faculty_id": 1, "role": "PI"}, {"faculty_id": 2, "role": "BENEFICIARY"}]))
    assert sponsored.status_code == consultancy.status_code == internal.status_code == 201
    assert Decimal(str(internal.json()["amount_utilized"])) == Decimal("0.00")
    assert {member["role"] for member in internal.json()["faculty"]} == {"PI", "BENEFICIARY"}

    duplicate = client.post("/funding-projects", json=funding(faculty=[{"faculty_id": 1, "role": "PI"}, {"faculty_id": 1, "role": "PI"}]))
    missing_pi = client.post("/funding-projects", json=funding(faculty=[{"faculty_id": 1, "role": "CO_PI"}]))
    invalid_dates = client.post("/funding-projects", json=funding(start_date="2026-09-01", end_date="2026-08-31"))
    assert duplicate.status_code == missing_pi.status_code == invalid_dates.status_code == 422
    assert client.get("/funding-project-options").json()["categories"] == ["SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT"]


def test_funding_dashboard_filters_pagination_and_lifecycle(setup):
    client, _, _ = setup
    for index in range(12):
        response = client.post("/funding-projects", json=funding(
            "SPONSORED_RESEARCH", "SUBMITTED" if index < 2 else "ONGOING",
            title=f"Project {index}", reference_number=f"P-{index}",
        ))
        assert response.status_code == 201

    period = "category=SPONSORED_RESEARCH&from_date=2026-07-01&to_date=2026-12-31"
    first = client.get("/funding-projects?" + period + "&page=1&page_size=10").json()
    second = client.get("/funding-projects?" + period + "&page=2&page_size=10").json()
    all_rows = client.get("/funding-projects?" + period + "&page=1&page_size=all").json()
    dashboard = client.get("/funding-dashboard?" + period).json()
    assert first["total"] == all_rows["total"] == dashboard["totals"]["total"] == 12
    assert len(first["items"]) == 10 and len(second["items"]) == 2 and len(all_rows["items"]) == 12
    assert {item["id"] for item in first["items"] + second["items"]} == {item["id"] for item in all_rows["items"]}
    assert dashboard["totals"]["submitted_under_review"] == 2 and dashboard["totals"]["sanctioned"] == 10
    assert client.get("/funding-projects?" + period + "&metric=ongoing&page=1&page_size=all").json()["total"] == 10

    identity = first["items"][0]["id"]
    assert client.delete(f"/funding-projects/{identity}").status_code == 200
    assert client.get("/funding-projects?" + period + "&page=1&page_size=all").json()["total"] == 11
    assert client.get("/funding-projects?" + period + "&include_inactive=true&page=1&page_size=all").json()["total"] == 12
    assert client.post(f"/funding-projects/{identity}/reactivate").status_code == 200


def test_funding_update_and_evidence_preservation(setup):
    client, _, _ = setup
    created = client.post("/funding-projects", json=funding("CONSULTANCY", "SANCTIONED", title="Original", amount_received="1000.10"))
    assert created.status_code == 201
    identity = created.json()["id"]
    evidence = client.post(
        f"/funding-projects/{identity}/evidence",
        data={"evidence_type": "AGREEMENT"},
        files={"file": ("agreement.pdf", b"%PDF-funding", "application/pdf")},
    )
    assert evidence.status_code == 201
    updated = client.put(f"/funding-projects/{identity}", json=funding(
        "CONSULTANCY", "COMPLETED", title="Updated", amount_received="1000.10", amount_utilized="900.00",
        faculty=[{"faculty_id": 1, "role": "PI"}, {"faculty_id": 1, "role": "BENEFICIARY"}, {"faculty_id": 2, "role": "CO_PI"}],
    ))
    assert updated.status_code == 200 and updated.json()["id"] == identity
    assert len(client.get(f"/funding-projects/{identity}/evidence").json()) == 1
    other = client.post("/funding-projects", json=funding("CONSULTANCY", "DRAFT", title="Other")).json()
    assert client.delete(f"/funding-projects/{other['id']}/evidence/{evidence.json()['id']}").status_code == 404
    assert client.delete(f"/funding-projects/{identity}/evidence/{evidence.json()['id']}").status_code == 200
