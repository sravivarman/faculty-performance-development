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
        "proposed_amount": None,
        "sanctioned_amount": None,
        "contract_amount": None,
        "amount_received": None,
        "amount_utilized": None,
        "reference_number": None,
        "status": status,
        "faculty": [{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "CO_PI"}],
    }
    if status in ("SANCTIONED", "ONGOING", "COMPLETED"):
        value.update({"sanction_date": "2026-08-10", "start_date": "2026-08-15", "sanctioned_amount": "125000.50"})
    value.update(changes)
    return value


def test_funding_categories_associations_and_validation(setup):
    client, _, _ = setup
    sponsored = client.post("/funding-projects", json=funding("SPONSORED_RESEARCH", "SANCTIONED"))
    consultancy = client.post("/funding-projects", json=funding("CONSULTANCY", "ONGOING", title="Industry study", amount_received="50000.25"))
    internal = client.post("/funding-projects", json=funding("INTERNAL_GRANT", "COMPLETED", title="Seed support", amount_utilized="0.00", faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "BENEFICIARY"}]))
    assert sponsored.status_code == consultancy.status_code == internal.status_code == 201
    assert Decimal(str(internal.json()["amount_utilized"])) == Decimal("0.00")
    assert {member["role"] for member in internal.json()["faculty"]} == {"MEMBER_PI", "BENEFICIARY"}

    duplicate = client.post("/funding-projects", json=funding(faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 1, "role": "MEMBER_PI"}]))
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
        faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 1, "role": "BENEFICIARY"}, {"faculty_id": 2, "role": "CO_PI"}],
    ))
    assert updated.status_code == 200 and updated.json()["id"] == identity
    assert len(client.get(f"/funding-projects/{identity}/evidence").json()) == 1
    other = client.post("/funding-projects", json=funding("CONSULTANCY", "DRAFT", title="Other")).json()
    assert client.delete(f"/funding-projects/{other['id']}/evidence/{evidence.json()['id']}").status_code == 404
    assert client.delete(f"/funding-projects/{identity}/evidence/{evidence.json()['id']}").status_code == 200


def manual_investigator(name, role, department="EEE", institution="Vardhaman College of Engineering"):
    return {"role": role, "investigator_name": name, "department_name": department, "institution_name": institution}


def test_manual_and_linked_pi_copi_investigators(setup):
    client, factory, _ = setup
    from backend.models import Faculty

    with factory() as db:
        db.add(Faculty(id=3, employee_id="C", name="Faculty C", name_variants=[]))
        db.commit()

    manual_pi = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "SUBMITTED", title="Manual PI", faculty=[
            manual_investigator("Dr External PI", "MEMBER_PI", "CSE", "External University"),
            {"faculty_id": 1, "role": "CO_PI"},
        ],
    ))
    linked_pi = client.post("/funding-projects", json=funding(
        "CONSULTANCY", "DRAFT", title="Linked PI", faculty=[
            {"faculty_id": 1, "role": "MEMBER_PI"},
            manual_investigator("Dr External Co-PI", "CO_PI", "ECE", "Partner Institute"),
            manual_investigator("Dr Second Co-PI", "CO_PI", "EEE", "Another Institute"),
        ],
    ))
    linked_copis = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "DRAFT", title="Multiple linked Co-PIs", faculty=[
            {"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "CO_PI"}, {"faculty_id": 3, "role": "CO_PI"},
        ],
    ))
    assert manual_pi.status_code == linked_pi.status_code == linked_copis.status_code == 201
    detail = client.get(f"/funding-projects/{manual_pi.json()['id']}").json()
    pi = next(member for member in detail["faculty"] if member["role"] == "MEMBER_PI")
    assert pi["faculty_id"] is None and pi["faculty_name"] == "Dr External PI"
    assert pi["department_name"] == "CSE" and pi["institution_name"] == "External University"
    assert pi["agency_role_label"] is None
    assert {member["faculty_id"] for member in detail["faculty"] if member["role"] == "CO_PI"} == {1}

    period = "category=SPONSORED_RESEARCH&from_date=2026-07-01&to_date=2026-12-31"
    dashboard = client.get("/funding-dashboard?" + period).json()
    faculty_ids = {row["id"] for row in dashboard["faculty"]}
    assert 1 in faculty_ids and 2 in faculty_ids and 3 in faculty_ids
    assert len(dashboard["faculty"]) == 3


def test_manual_investigator_validation_and_internal_grant_beneficiaries(setup):
    client, _, _ = setup
    missing_pi = client.post("/funding-projects", json=funding(faculty=[manual_investigator("Dr Co-PI", "CO_PI")]))
    multiple_pi = client.post("/funding-projects", json=funding(faculty=[manual_investigator("Dr One", "MEMBER_PI"), manual_investigator("Dr Two", "MEMBER_PI")]))
    duplicate_lead = client.post("/funding-projects", json=funding(faculty=[manual_investigator("Dr One", "LEAD_PI"), manual_investigator("Dr Two", "LEAD_PI")]))
    missing_identity = client.post("/funding-projects", json=funding(faculty=[{"role": "MEMBER_PI"}]))
    invalid_linked = client.post("/funding-projects", json=funding(faculty=[{"faculty_id": 999, "role": "MEMBER_PI"}]))
    internal = client.post("/funding-projects", json=funding("INTERNAL_GRANT", "DRAFT", faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "BENEFICIARY"}]))
    assert missing_pi.status_code == missing_identity.status_code == invalid_linked.status_code == duplicate_lead.status_code == 422
    assert multiple_pi.status_code == 201
    assert internal.status_code == 201
    assert {member["role"] for member in internal.json()["faculty"]} == {"MEMBER_PI", "BENEFICIARY"}


def test_multiple_pi_roles_agency_titles_reordering_and_faculty_attribution(setup):
    client, factory, _ = setup
    from backend.models import Faculty

    with factory() as db:
        db.add(Faculty(id=3, employee_id="C", name="Faculty C", name_variants=[]))
        db.commit()

    investigators = [
        {"faculty_id": 1, "role": "LEAD_PI", "agency_role_label": "Lead PI"},
        {"faculty_id": 2, "role": "MEMBER_PI", "agency_role_label": "Member PI"},
        {"faculty_id": 3, "role": "MEMBER_PI", "agency_role_label": "Member PI"},
        manual_investigator("Dr External PI", "MEMBER_PI", "EEE", "Partner University"),
        manual_investigator("Dr Co-PI", "CO_PI", "ECE", "Consortium Institute"),
        {"faculty_id": 2, "role": "CO_PI", "agency_role_label": "Co-Investigator"},
        manual_investigator("Dr Administrative", "ADMIN_PI", "Research Office", "VCE"),
    ]
    created = client.post("/funding-projects", json=funding("SPONSORED_RESEARCH", "SUBMITTED", title="Consortium project", faculty=investigators))
    assert created.status_code == 201
    identity = created.json()["id"]
    detail = client.get(f"/funding-projects/{identity}").json()
    assert [row["role"] for row in detail["faculty"]] == [row["role"] for row in investigators]
    assert detail["faculty"][0]["agency_role_label"] == "Lead PI" and detail["faculty"][0]["is_designated_lead"] is True
    assert detail["faculty"][3]["faculty_id"] is None and detail["faculty"][3]["institution_name"] == "Partner University"

    revised = [investigators[1], investigators[0], *investigators[2:]]
    updated = client.put(f"/funding-projects/{identity}", json=funding("SPONSORED_RESEARCH", "SUBMITTED", title="Consortium project", faculty=revised))
    assert updated.status_code == 200 and updated.json()["id"] == identity
    reloaded = client.get(f"/funding-projects/{identity}").json()
    assert [row["faculty_name"] for row in reloaded["faculty"][:2]] == ["Faculty B", "Faculty A"]

    without_lead = [{**investigators[0], "role": "MEMBER_PI"}, *investigators[1:]]
    updated = client.put(f"/funding-projects/{identity}", json=funding("SPONSORED_RESEARCH", "SUBMITTED", title="Consortium project", faculty=without_lead))
    assert updated.status_code == 200
    switched = client.get(f"/funding-projects/{identity}").json()
    assert all(not row["is_designated_lead"] for row in switched["faculty"])
    assert switched["faculty"][0]["agency_role_label"] == "Lead PI"

    dashboard = client.get("/funding-dashboard?category=SPONSORED_RESEARCH&from_date=2026-07-01&to_date=2026-12-31").json()
    linked = {row["id"]: row for row in dashboard["faculty"]}
    assert dashboard["totals"]["total"] == 1
    assert linked[1]["role_lead_pi"] == 0 and linked[1]["role_member_pi"] == 1 and linked[2]["role_member_pi"] == 1 and linked[2]["role_co_pi"] == 1
    assert dashboard["role_counts"]["MEMBER_PI"] == 4 and dashboard["role_counts"]["CO_PI"] == 2


def test_funding_dashboard_awards_and_faculty_contributors_are_distinct(setup):
    client, _, _ = setup
    submitted_one = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "SUBMITTED", title="Proposal one", sanctioned_amount="4275149.00",
        faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, manual_investigator("Dr External PI", "MEMBER_PI")],
    ))
    submitted_two = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "UNDER_REVIEW", title="Proposal two", sanctioned_amount="4467500.00",
        faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "CO_PI"}],
    ))
    awarded = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "SANCTIONED", title="Awarded project", sanctioned_amount="123456.78",
        faculty=[
            {"faculty_id": 1, "role": "LEAD_PI", "agency_role_label": "Lead PI"},
            {"faculty_id": 2, "role": "MEMBER_PI", "agency_role_label": "Member PI"},
            manual_investigator("Dr Administrative", "ADMIN_PI"),
            {"faculty_id": 2, "role": "CO_PI"},
        ],
    ))
    assert submitted_one.status_code == submitted_two.status_code == awarded.status_code == 201

    period = "category=SPONSORED_RESEARCH&from_date=2026-07-01&to_date=2026-12-31"
    dashboard = client.get("/funding-dashboard?" + period).json()
    contributors = {person["id"]: person for person in dashboard["faculty"]}
    assert dashboard["totals"]["total"] == 3
    assert dashboard["totals"]["faculty_contributors"] == 2
    assert contributors[1]["projects"] == 3 and contributors[2]["projects"] == 2
    assert contributors[1]["department"] == "CSE" and "Lead PI" in contributors[1]["roles"]
    assert Decimal(str(dashboard["totals"]["sanctioned_amount"])) == Decimal("123456.78")

    financial_records = client.get("/funding-projects?" + period + "&metric=sanctioned_amount&page=1&page_size=all").json()
    assert financial_records["total"] == 1
    assert financial_records["items"][0]["id"] == awarded.json()["id"]
    assert Decimal(str(financial_records["items"][0]["sanctioned_amount"])) == Decimal("123456.78")

    detail = client.get(f"/funding-projects/{awarded.json()['id']}").json()
    pis = [member for member in detail["faculty"] if member["role"] in {"LEAD_PI", "MEMBER_PI", "ADMIN_PI"}]
    assert [(member["faculty_name"], member["role"]) for member in pis] == [
        ("Faculty A", "LEAD_PI"), ("Faculty B", "MEMBER_PI"), ("Dr Administrative", "ADMIN_PI"),
    ]


def test_category_specific_financial_amounts_are_precise_and_not_duplicated(setup):
    client, _, _ = setup
    period = "from_date=2026-07-01&to_date=2026-12-31"

    submitted = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "SUBMITTED", title="Requested only",
        proposed_amount="200000.25", sanctioned_amount=None,
        faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "CO_PI"}],
    ))
    sanctioned = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "SANCTIONED", title="Awarded below proposal",
        proposed_amount="300000.75", sanctioned_amount="245000.50",
        faculty=[{"faculty_id": 1, "role": "LEAD_PI"}, {"faculty_id": 2, "role": "MEMBER_PI"}],
    ))
    consultancy = client.post("/funding-projects", json=funding(
        "CONSULTANCY", "ONGOING", title="Consultancy award",
        contract_amount="75000.55", amount_received="0.00",
        faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "CO_PI"}],
    ))
    internal = client.post("/funding-projects", json=funding(
        "INTERNAL_GRANT", "COMPLETED", title="Seed grant",
        sanctioned_amount="50000.10", amount_utilized="0.00",
        faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "BENEFICIARY"}],
    ))
    assert submitted.status_code == sanctioned.status_code == consultancy.status_code == internal.status_code == 201
    assert Decimal(str(submitted.json()["proposed_amount"])) == Decimal("200000.25")
    assert submitted.json()["sanctioned_amount"] is None
    assert Decimal(str(sanctioned.json()["proposed_amount"])) == Decimal("300000.75")
    assert Decimal(str(sanctioned.json()["sanctioned_amount"])) == Decimal("245000.50")
    assert Decimal(str(consultancy.json()["contract_amount"])) == Decimal("75000.55")
    assert Decimal(str(consultancy.json()["amount_received"])) == Decimal("0.00")
    assert Decimal(str(internal.json()["sanctioned_amount"])) == Decimal("50000.10")
    assert Decimal(str(internal.json()["amount_utilized"])) == Decimal("0.00")

    sponsored_dashboard = client.get("/funding-dashboard?category=SPONSORED_RESEARCH&" + period).json()
    consultancy_dashboard = client.get("/funding-dashboard?category=CONSULTANCY&" + period).json()
    internal_dashboard = client.get("/funding-dashboard?category=INTERNAL_GRANT&" + period).json()
    assert Decimal(str(sponsored_dashboard["totals"]["sanctioned_amount"])) == Decimal("245000.50")
    assert Decimal(str(consultancy_dashboard["totals"]["contract_value"])) == Decimal("75000.55")
    assert Decimal(str(consultancy_dashboard["totals"]["amount_received"])) == Decimal("0.00")
    assert Decimal(str(internal_dashboard["totals"]["sanctioned_amount"])) == Decimal("50000.10")
    assert Decimal(str(internal_dashboard["totals"]["amount_utilized"])) == Decimal("0.00")

    sanctioned_rows = client.get("/funding-projects?category=SPONSORED_RESEARCH&" + period + "&metric=sanctioned_amount&page=1&page_size=all").json()
    contract_rows = client.get("/funding-projects?category=CONSULTANCY&" + period + "&metric=contract_value&page=1&page_size=all").json()
    assert sanctioned_rows["total"] == 1 and sanctioned_rows["items"][0]["id"] == sanctioned.json()["id"]
    assert contract_rows["total"] == 1 and contract_rows["items"][0]["id"] == consultancy.json()["id"]


def test_historical_pre_sanction_amount_is_preserved_without_automatic_reclassification(setup):
    client, _, _ = setup
    historical = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "SUBMITTED", title="Historical ambiguous budget",
        sanctioned_amount="4275149.00", proposed_amount=None,
    ))
    assert historical.status_code == 201
    detail = client.get(f"/funding-projects/{historical.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["proposed_amount"] is None
    assert Decimal(str(detail.json()["sanctioned_amount"])) == Decimal("4275149.00")
    dashboard = client.get("/funding-dashboard?category=SPONSORED_RESEARCH&from_date=2026-07-01&to_date=2026-12-31").json()
    assert Decimal(str(dashboard["totals"]["sanctioned_amount"])) == Decimal("0")


def test_legacy_investigator_roles_are_preserved_but_not_available_for_new_assignments(setup):
    client, factory, _ = setup
    from backend.models import FundingProject

    created = client.post("/funding-projects", json=funding(
        "SPONSORED_RESEARCH", "DRAFT", title="Historical-role project",
        faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "CO_PI"}],
    ))
    assert created.status_code == 201
    identity = created.json()["id"]
    with factory() as db:
        project = db.get(FundingProject, identity)
        project.faculty[0].role = "PI"
        project.faculty[1].role = "CO_INVESTIGATOR"
        db.commit()

    historical = client.get(f"/funding-projects/{identity}")
    assert historical.status_code == 200
    assert [member["role"] for member in historical.json()["faculty"]] == ["PI", "CO_INVESTIGATOR"]
    preserved = client.put(f"/funding-projects/{identity}", json={**funding("SPONSORED_RESEARCH", "DRAFT", title="Historical-role project"), "faculty": historical.json()["faculty"]})
    assert preserved.status_code == 200
    assert [member["role"] for member in client.get(f"/funding-projects/{identity}").json()["faculty"]] == ["PI", "CO_INVESTIGATOR"]

    new_legacy_pi = client.post("/funding-projects", json=funding(faculty=[{"faculty_id": 1, "role": "PI"}]))
    new_legacy_co_investigator = client.post("/funding-projects", json=funding(faculty=[{"faculty_id": 1, "role": "MEMBER_PI"}, {"faculty_id": 2, "role": "CO_INVESTIGATOR"}]))
    assert new_legacy_pi.status_code == new_legacy_co_investigator.status_code == 422
