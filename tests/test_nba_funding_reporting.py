from datetime import date

from backend.models import AcademicYear, FundingProject


def project(title, category="SPONSORED_RESEARCH", sanction_date="2026-07-01", proposal_date="2026-06-01"):
    return {
        "title": title,
        "category": category,
        "department": "CSE",
        "funding_agency": "Research Council",
        "proposal_submission_date": proposal_date,
        "sanction_date": sanction_date,
        "start_date": sanction_date,
        "end_date": None,
        "proposed_amount": "100.00",
        "sanctioned_amount": "90.00",
        "contract_amount": "80.00",
        "amount_received": "0.00",
        "amount_utilized": None,
        "status": "SANCTIONED",
        "faculty": [{"faculty_id": 1, "role": "MEMBER_PI"}],
    }


def test_nba_reporting_reuses_master_year_boundaries_and_relative_years(setup):
    client, factory, _ = setup
    with factory() as db:
        db.add(AcademicYear(id=3, name="2025-26", start_date=date(2025, 7, 1), end_date=date(2026, 6, 30)))
        db.commit()

    start = client.post("/funding-projects", json=project("CAY start", sanction_date="2026-07-01"))
    end = client.post("/funding-projects", json=project("CAY end", sanction_date="2027-06-30"))
    previous = client.post("/funding-projects", json=project("Previous CAY", sanction_date="2025-07-01"))
    outside = client.post("/funding-projects", json=project("Outside window", sanction_date="2027-07-01"))
    assert start.status_code == end.status_code == previous.status_code == outside.status_code == 201

    options = client.get("/nba/funding-reporting-options")
    assert options.status_code == 200
    assert {year["id"] for year in options.json()["academic_years"]} == {1, 2, 3}
    assert {report["category"] for report in options.json()["reports"]} == {"SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT"}

    preview = client.get("/nba/funding-reports/SPONSORED_RESEARCH?reference_academic_year_id=1&relative_year_count=3")
    assert preview.status_code == 200
    payload = preview.json()
    assert [period["code"] for period in payload["periods"]] == ["CAY", "CAYm1"]
    assert [period["academic_year"]["id"] for period in payload["periods"]] == [1, 3]
    assert {record["id"] for record in payload["periods"][0]["records"]} == {start.json()["id"], end.json()["id"]}
    assert {record["id"] for record in payload["periods"][1]["records"]} == {previous.json()["id"]}
    assert payload["outside_selected_relative_years"] == 1


def test_nba_reporting_flags_missing_dates_and_supports_explicit_policy_override(setup):
    client, factory, _ = setup
    with factory() as db:
        db.add(AcademicYear(id=3, name="2025-26", start_date=date(2025, 7, 1), end_date=date(2026, 6, 30)))
        db.commit()

    override = client.post("/funding-projects", json=project(
        "Policy override", sanction_date="2026-07-01", proposal_date="2025-07-01"
    ))
    missing = client.post("/funding-projects", json=project("Missing sanction date"))
    submitted_without_date = client.post("/funding-projects", json={
        **project("Submitted without sanction date", sanction_date=None),
        "status": "SUBMITTED",
    })
    assert override.status_code == missing.status_code == submitted_without_date.status_code == 201
    with factory() as db:
        db.get(FundingProject, missing.json()["id"]).sanction_date = None
        db.commit()

    default_preview = client.get("/nba/funding-reports/SPONSORED_RESEARCH?reference_academic_year_id=1&relative_year_count=2")
    assert default_preview.status_code == 200
    assert default_preview.json()["policy"]["date_basis"] == "SANCTION_DATE"
    incomplete = {record["id"]: record for record in default_preview.json()["incomplete_records"]}
    assert incomplete[missing.json()["id"]] == {
        "id": missing.json()["id"], "title": "Missing sanction date", "status": "SANCTIONED",
        "missing_field": "sanction_date", "missing_label": "Sanction date", "eligible_for_selected_policy": True,
    }
    assert incomplete[submitted_without_date.json()["id"]] == {
        "id": submitted_without_date.json()["id"], "title": "Submitted without sanction date", "status": "SUBMITTED",
        "missing_field": "sanction_date", "missing_label": "Sanction date", "eligible_for_selected_policy": False,
    }

    overridden_preview = client.get("/nba/funding-reports/SPONSORED_RESEARCH?reference_academic_year_id=1&relative_year_count=2&date_basis=PROPOSAL_SUBMISSION_DATE")
    assert overridden_preview.status_code == 200
    periods = overridden_preview.json()["periods"]
    assert periods[0]["count"] == 0
    assert {record["id"] for record in periods[1]["records"]} == {override.json()["id"]}


def test_nba_funding_report_categories_have_explicit_tables_and_no_year_writes(setup):
    client, _, _ = setup
    before = client.get("/masters").json()["academic_years"]
    expected = {
        "SPONSORED_RESEARCH": "NBA Table 6.2.4.1 — Sponsored Research",
        "CONSULTANCY": "NBA Table 6.2.5.1 — Consultancy Projects",
        "INTERNAL_GRANT": "NBA Table 6.2.6.1 — Seed Money / Internal Grants",
    }
    for category, table in expected.items():
        response = client.get(f"/nba/funding-reports/{category}?reference_academic_year_id=1")
        assert response.status_code == 200
        assert response.json()["table"] == table
    assert client.get("/masters").json()["academic_years"] == before
