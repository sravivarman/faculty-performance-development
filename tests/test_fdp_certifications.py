def activity():
    return {"title":"Faculty Development Programme","activity_type":"FDP","organizing_institution":"Vardhaman","start_date":"2026-08-01","end_date":"2026-08-03","duration_value":3,"duration_unit":"DAYS","participants":[{"faculty_id":1,"role":"ATTENDEE"},{"faculty_id":2,"role":"RESOURCE_PERSON"}],"speakers":[{"name":"External Speaker","organization":"Industry"},{"name":"Second Speaker"}]}


def test_fdp_multiple_people_and_filters(setup):
    client, _, _ = setup
    created = client.post("/fdp-activities", json=activity())
    assert created.status_code == 201
    assert len(created.json()["participants"]) == 2
    assert len(created.json()["speakers"]) == 2
    assert len(client.get("/fdp-activities?from_date=2026-07-01&to_date=2026-12-31&role=RESOURCE_PERSON").json()) == 1
    assert client.post("/fdp-activities", json={**activity(),"participants":[{"faculty_id":1,"role":"ATTENDEE"},{"faculty_id":1,"role":"ATTENDEE"}]}).status_code == 422
    assert client.delete(f"/fdp-activities/{created.json()['id']}").status_code == 200


def test_fdp_participation_roles_are_limited_to_three_approved_values(setup):
    client, factory, _ = setup
    from backend.models import Faculty

    with factory() as db:
        db.add(Faculty(id=3, employee_id="C", name="Faculty C", name_variants=[]))
        db.commit()

    participants = [
        {"faculty_id": 1, "role": "ATTENDEE"},
        {"faculty_id": 2, "role": "RESOURCE_PERSON"},
        {"faculty_id": 3, "role": "COORDINATOR"},
        {"faculty_id": 1, "role": "COORDINATOR"},
    ]
    created = client.post("/fdp-activities", json={**activity(), "participants": participants})
    assert created.status_code == 201
    assert {(row["faculty_id"], row["role"]) for row in created.json()["participants"]} == {
        (1, "ATTENDEE"), (1, "COORDINATOR"), (2, "RESOURCE_PERSON"), (3, "COORDINATOR"),
    }
    assert client.get("/fdp-options").json()["roles"] == ["ATTENDEE", "RESOURCE_PERSON", "COORDINATOR"]
    assert client.get("/fdp-activities?role=COORDINATOR").status_code == 200
    assert client.post("/fdp-activities", json={**activity(), "participants": [*participants, {"faculty_id": 1, "role": "ATTENDEE"}]}).status_code == 422
    for retired in ("ORGANIZER", "CONDUCTOR", "PARTICIPANT", "TRAINEE", "COLLABORATOR", "OTHER"):
        assert client.post("/fdp-activities", json={**activity(), "participants": [{"faculty_id": 1, "role": retired}]}).status_code == 422
        assert client.get("/fdp-activities?role=" + retired).status_code == 422
        assert client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31&role=" + retired).status_code == 422

    dashboard = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["role_counts"] == {"ATTENDEE": 1, "RESOURCE_PERSON": 1, "COORDINATOR": 2}
    assert dashboard["totals"]["activities"] == 1 and dashboard["totals"]["faculty_contributors"] == 3


def test_fdp_many_participants_preserve_one_activity_evidence_and_distinct_counts(setup):
    client, factory, _ = setup
    from backend.models import Faculty

    with factory() as db:
        db.add_all([
            Faculty(id=identity, employee_id=f"E{identity}", name=f"Faculty {identity}", name_variants=[], is_active=identity != 12)
            for identity in range(3, 14)
        ])
        db.commit()

    participants = [{"faculty_id": identity, "role": "ATTENDEE"} for identity in range(1, 13)]
    participants.append({"faculty_id": 1, "role": "COORDINATOR"})
    payload = {**activity(), "title": "Bulk participant activity", "participants": participants}
    created = client.post("/fdp-activities", json=payload)
    assert created.status_code == 201
    identity = created.json()["id"]
    assert len(created.json()["participants"]) == 13
    assert {row["faculty_id"] for row in created.json()["participants"]} == set(range(1, 13))

    evidence = client.post(
        f"/fdp-activities/{identity}/evidence",
        data={"evidence_type": "PROGRAM"},
        files={"file": ("agenda.pdf", b"%PDF-bulk", "application/pdf")},
    )
    assert evidence.status_code == 201

    updated_participants = [{"faculty_id": faculty_id, "role": "ATTENDEE"} for faculty_id in range(1, 12)]
    updated_participants.extend([{"faculty_id": 13, "role": "ATTENDEE"}, {"faculty_id": 1, "role": "COORDINATOR"}])
    updated = client.put(f"/fdp-activities/{identity}", json={**payload, "participants": updated_participants})
    assert updated.status_code == 200 and updated.json()["id"] == identity
    detail = client.get(f"/fdp-activities/{identity}").json()
    expected_participants = {(faculty_id, "ATTENDEE") for faculty_id in range(1, 12)} | {(13, "ATTENDEE"), (1, "COORDINATOR")}
    assert {(row["faculty_id"], row["role"]) for row in detail["participants"]} == expected_participants
    assert len(client.get(f"/fdp-activities/{identity}/evidence").json()) == 1
    assert client.post("/fdp-activities", json={**payload, "title": "Duplicate participant", "participants": [*participants, {"faculty_id": 1, "role": "ATTENDEE"}]}).status_code == 422

    dashboard = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["totals"]["activities"] == 1 and dashboard["totals"]["faculty_contributors"] == 12
    assert dashboard["role_counts"]["ATTENDEE"] == 12 and dashboard["role_counts"]["COORDINATOR"] == 1
    performance = {row["id"]: row for row in dashboard["faculty_performance"]}
    assert performance[1]["activities"] == 1 and performance[1]["participations"] == 2


def test_certification_completed_and_in_progress(setup):
    client, _, _ = setup
    completed={"faculty_id":1,"name":"MOOC","category":"MOOC","provider":"NPTEL","status":"COMPLETED","completion_date":"2026-08-03","issue_date":"2026-08-04"}
    assert client.post("/certifications",json=completed).status_code == 201
    in_progress={"faculty_id":2,"name":"Course","category":"OTHER","provider":"Provider","status":"IN_PROGRESS"}
    assert client.post("/certifications",json=in_progress).status_code == 201
    dashboard=client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["totals"]["completed"] == 1 and dashboard["totals"]["in_progress"] == 1


def test_certification_kpi_drilldown_queries_match_completed_and_current_work(setup):
    client, _, _ = setup
    created = {}
    for category, faculty_id in (("NPTEL_SWAYAM", 1), ("MOOC", 2), ("OTHER", 1)):
        response = client.post("/certifications", json={
            "faculty_id": faculty_id, "name": category, "category": category, "provider": "Provider",
            "status": "COMPLETED", "completion_date": "2026-08-01",
        })
        assert response.status_code == 201
        created[category] = response.json()["id"]
    current = client.post("/certifications", json={
        "faculty_id": 2, "name": "Current work", "category": "MOOC", "provider": "Provider", "status": "IN_PROGRESS",
    }).json()

    dashboard = client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["totals"] == {"certifications":3, "completed":3, "in_progress":1, "faculty_contributors":2}
    assert dashboard["categories"] == {"NPTEL_SWAYAM":1, "MOOC":1, "OTHER":1}
    completed = client.get("/certifications?from_date=2026-07-01&to_date=2026-12-31&status=COMPLETED&page=1&page_size=10").json()
    assert completed["total"] == 3 and {row["id"] for row in completed["items"]} == set(created.values())
    for category, identity in created.items():
        filtered = client.get(f"/certifications?from_date=2026-07-01&to_date=2026-12-31&status=COMPLETED&category={category}&page=1&page_size=10").json()
        assert filtered["total"] == 1 and filtered["items"][0]["id"] == identity
    in_progress = client.get("/certifications?from_date=2026-07-01&to_date=2026-12-31&status=IN_PROGRESS&current_in_progress=true&page=1&page_size=10").json()
    assert in_progress["total"] == 1 and in_progress["items"][0]["id"] == current["id"]
    faculty = client.get("/certifications?from_date=2026-07-01&to_date=2026-12-31&status=COMPLETED&faculty_id=1&page=1&page_size=10").json()
    assert faculty["total"] == 2 and {row["id"] for row in faculty["items"]} == {created["NPTEL_SWAYAM"], created["OTHER"]}


def test_dashboard_summaries_are_independent_of_kpi_record_queries(setup):
    """The overview uses a summary endpoint independently from drill-down lists."""
    client, _, _ = setup
    fdp = client.post("/fdp-activities", json=activity()).json()
    workshop = client.post("/fdp-activities", json={
        **activity(), "title": "Workshop drill-down", "activity_type": "WORKSHOP",
    }).json()
    certification = client.post("/certifications", json={
        "faculty_id": 1, "name": "Completed drill-down", "category": "MOOC",
        "provider": "Provider", "status": "COMPLETED", "completion_date": "2026-08-01",
    }).json()
    current = client.post("/certifications", json={
        "faculty_id": 2, "name": "Current drill-down", "category": "OTHER",
        "provider": "Provider", "status": "IN_PROGRESS",
    }).json()
    period = "from_date=2026-07-01&to_date=2026-12-31"

    fdp_summary = client.get(f"/fdp-dashboard?{period}").json()
    assert fdp_summary["totals"]["activities"] == 2
    assert client.get(f"/fdp-activities?{period}&activity_type=FDP&page=1&page_size=10").json()["items"][0]["id"] == fdp["id"]
    assert client.get(f"/fdp-activities?{period}&activity_type=WORKSHOP&page=1&page_size=10").json()["items"][0]["id"] == workshop["id"]
    assert client.get(f"/fdp-activities?{period}&activity_type=STTP&page=1&page_size=10").json()["total"] == 0
    assert client.get(f"/fdp-dashboard?{period}").json() == fdp_summary

    certification_summary = client.get(f"/certification-dashboard?{period}").json()
    assert certification_summary["totals"] == {"certifications": 1, "completed": 1, "in_progress": 1, "faculty_contributors": 1}
    completed = client.get(f"/certifications?{period}&status=COMPLETED&category=MOOC&page=1&page_size=10").json()
    current_page = client.get(f"/certifications?{period}&status=IN_PROGRESS&current_in_progress=true&page=1&page_size=10").json()
    assert completed["items"][0]["id"] == certification["id"]
    assert current_page["items"][0]["id"] == current["id"]
    assert client.get(f"/certification-dashboard?{period}").json() == certification_summary


def test_certification_dashboard_dates_completed_but_not_current_work(setup):
    client, _, _ = setup
    inside={"faculty_id":1,"name":"Inside","category":"MOOC","provider":"NPTEL","status":"COMPLETED","completion_date":"2026-07-01"}
    outside={"faculty_id":1,"name":"Outside","category":"MOOC","provider":"NPTEL","status":"COMPLETED","completion_date":"2026-06-30"}
    progress={"faculty_id":2,"name":"Ongoing","category":"OTHER","provider":"Provider","status":"IN_PROGRESS"}
    assert client.post("/certifications",json=inside).status_code == 201
    assert client.post("/certifications",json=outside).status_code == 201
    ongoing=client.post("/certifications",json=progress).json()
    assert client.delete(f"/certifications/{ongoing['id']}").status_code == 200
    dashboard=client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["totals"]["completed"] == 1
    assert dashboard["totals"]["in_progress"] == 0


def test_fdp_update_filters_pagination_and_faculty_details(setup):
    client, _, _ = setup
    payload=activity()
    created=client.post("/fdp-activities",json=payload).json()
    updated={**payload,"title":"Updated activity","participants":[{"faculty_id":1,"role":"COORDINATOR"},{"faculty_id":2,"role":"RESOURCE_PERSON"}],"speakers":[{"name":"Edited"},{"name":"New"}]}
    response=client.put(f"/fdp-activities/{created['id']}",json=updated)
    assert response.status_code == 200 and response.json()["id"] == created["id"]
    detail=client.get(f"/fdp-activities/{created['id']}").json()
    assert detail["title"] == "Updated activity" and len(detail["participants"]) == 2 and len(detail["speakers"]) == 2
    page=client.get("/fdp-activities?from_date=2026-07-01&to_date=2026-12-31&search=Updated&activity_type=FDP&faculty_id=1&role=COORDINATOR&page=1&page_size=10").json()
    assert page["total"] == 1 and page["items"][0]["id"] == created["id"]
    profile=client.get("/research/faculty/1?from_date=2026-07-01&to_date=2026-12-31").json()
    assert profile["fdp"][0]["id"] == created["id"] and profile["fdp"][0]["role"] == "COORDINATOR"


def test_evidence_lifecycle_isolated_by_owner(setup):
    client, _, _ = setup
    activity_id=client.post("/fdp-activities",json=activity()).json()["id"]
    cert=client.post("/certifications",json={"faculty_id":1,"name":"Credential","category":"MOOC","provider":"NPTEL","status":"COMPLETED","completion_date":"2026-08-01"}).json()
    files={"file":("proof.pdf",b"%PDF-test","application/pdf")}
    fdp=client.post(f"/fdp-activities/{activity_id}/evidence",data={"evidence_type":"PROGRAM"},files=files)
    certification=client.post(f"/certifications/{cert['id']}/evidence",data={"evidence_type":"CERTIFICATE"},files=files)
    assert fdp.status_code == 201 and certification.status_code == 201
    assert len(client.get(f"/fdp-activities/{activity_id}/evidence").json()) == 1
    assert client.delete(f"/certifications/{cert['id']}/evidence/{fdp.json()['id']}").status_code == 404
    assert client.delete(f"/fdp-activities/{activity_id}/evidence/{fdp.json()['id']}").status_code == 200
    assert len(client.get(f"/certifications/{cert['id']}/evidence").json()) == 1


def test_fdp_reactivation_and_permanent_deletion_isolate_relations_and_evidence(setup):
    client, factory, tmp_path = setup
    from sqlalchemy import select
    from backend.models import EvidenceFile, Faculty, FdpChangeLog, FdpParticipant, FdpSpeaker

    deleted = client.post("/fdp-activities", json=activity()).json()
    retained = client.post("/fdp-activities", json={**activity(), "title": "Retained activity", "participants": [{"faculty_id": 2, "role": "COORDINATOR"}]}).json()
    for row, filename in ((deleted, "delete-me.pdf"), (retained, "keep-me.pdf")):
        response = client.post(
            f"/fdp-activities/{row['id']}/evidence",
            data={"evidence_type": "PROGRAM"},
            files={"file": (filename, b"%PDF-evidence", "application/pdf")},
        )
        assert response.status_code == 201

    assert client.delete(f"/fdp-activities/{deleted['id']}").status_code == 200
    soft_detail = client.get(f"/fdp-activities/{deleted['id']}").json()
    assert soft_detail["is_active"] is False and any(item["action"] == "DEACTIVATE" for item in soft_detail["change_log"])
    assert len(client.get(f"/fdp-activities/{deleted['id']}/evidence").json()) == 1
    inactive_dashboard = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert inactive_dashboard["totals"]["activities"] == 1

    restored = client.post(f"/fdp-activities/{deleted['id']}/reactivate")
    assert restored.status_code == 200 and restored.json()["id"] == deleted["id"] and restored.json()["is_active"] is True
    assert len(restored.json()["participants"]) == 2 and len(client.get(f"/fdp-activities/{deleted['id']}/evidence").json()) == 1
    active_dashboard = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert active_dashboard["totals"]["activities"] == 2

    permanent = client.delete(f"/fdp-activities/{deleted['id']}/permanent")
    assert permanent.status_code == 200 and permanent.json()["deleted"] == deleted["id"]
    assert permanent.json()["evidence_cleanup_failures"] == []
    assert client.get(f"/fdp-activities/{deleted['id']}").status_code == 404
    assert client.delete(f"/fdp-activities/{deleted['id']}/permanent").status_code == 404
    assert len(client.get(f"/fdp-activities/{retained['id']}/evidence").json()) == 1
    final_dashboard = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert final_dashboard["totals"]["activities"] == 1
    profile = client.get("/research/faculty/1?from_date=2026-07-01&to_date=2026-12-31").json()
    assert deleted["id"] not in {row["id"] for row in profile["fdp"]}

    with factory() as db:
        assert not db.scalars(select(FdpParticipant).where(FdpParticipant.activity_id == deleted["id"])).all()
        assert not db.scalars(select(FdpSpeaker).where(FdpSpeaker.activity_id == deleted["id"])).all()
        assert not db.scalars(select(FdpChangeLog).where(FdpChangeLog.activity_id == deleted["id"])).all()
        assert not db.scalars(select(EvidenceFile).where(EvidenceFile.fdp_activity_id == deleted["id"])).all()
        assert db.get(Faculty, 1) is not None
        assert db.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert len(list((tmp_path / "evidence").rglob("*.pdf"))) == 1


def test_fdp_permanent_deletion_reports_evidence_cleanup_failure(setup, monkeypatch):
    client, _, _ = setup
    import backend.fdp_certification_api as fdp_api

    created = client.post("/fdp-activities", json=activity()).json()
    assert client.post(
        f"/fdp-activities/{created['id']}/evidence",
        data={"evidence_type": "PROGRAM"},
        files={"file": ("locked.pdf", b"%PDF-locked", "application/pdf")},
    ).status_code == 201
    monkeypatch.setattr(fdp_api, "unlink_evidence_file", lambda _path: (_ for _ in ()).throw(OSError("file is locked")))

    response = client.delete(f"/fdp-activities/{created['id']}/permanent")
    assert response.status_code == 200
    assert response.json()["evidence_cleanup_failures"] == [{"evidence_id": 1, "filename": "locked.pdf", "reason": "file is locked"}]
    assert client.get(f"/fdp-activities/{created['id']}").status_code == 404


def test_certification_filters_pagination_edit_and_profile(setup):
    client, _, _ = setup
    first=client.post("/certifications",json={"faculty_id":1,"name":"Cloud Course","category":"MOOC","provider":"NPTEL","status":"COMPLETED","completion_date":"2026-07-01"}).json()
    client.post("/certifications",json={"faculty_id":2,"name":"Other","category":"OTHER","provider":"Provider","status":"IN_PROGRESS"})
    updated={**first,"name":"Cloud Course Updated","status":"COMPLETED","completion_date":"2026-07-01"}
    assert client.put(f"/certifications/{first['id']}",json=updated).json()["id"] == first["id"]
    filtered=client.get("/certifications?from_date=2026-07-01&to_date=2026-12-31&search=Updated&faculty_id=1&category=MOOC&status=COMPLETED&page=1&page_size=10").json()
    assert filtered["total"] == 1 and filtered["items"][0]["id"] == first["id"]
    assert isinstance(client.get("/certifications").json(),list)
    profile=client.get("/research/faculty/1?from_date=2026-07-01&to_date=2026-12-31").json()
    assert [x["id"] for x in profile["certifications"]] == [first["id"]]


def test_fdp_dashboard_types_other_group_and_distinct_people(setup):
    client, _, _ = setup
    base=activity()
    fdp=client.post("/fdp-activities",json=base).json()
    workshop=client.post("/fdp-activities",json={**base,"title":"Workshop","activity_type":"WORKSHOP","participants":[{"faculty_id":1,"role":"COORDINATOR"}],"speakers":[{"name":"One"},{"name":"Two"}]}).json()
    other=client.post("/fdp-activities",json={**base,"title":"Seminar","activity_type":"SEMINAR","participants":[{"faculty_id":1,"role":"ATTENDEE"},{"faculty_id":2,"role":"RESOURCE_PERSON"}]}).json()
    dashboard=client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["totals"] == {"activities":3,"faculty_contributors":2,"fdp":1,"sttp":0,"workshops":1,"webinars":0,"seminars":1,"internships":0,"industrial_training":0}
    other_page=client.get("/fdp-activities?from_date=2026-07-01&to_date=2026-12-31&activity_group=OTHER&page=1&page_size=10").json()
    assert other_page["total"] == 1 and other_page["items"][0]["id"] == other["id"]
    legacy=client.get("/fdp-activities?from_date=2026-07-01&to_date=2026-12-31").json()
    assert isinstance(legacy,list) and {x["id"] for x in legacy} == {fdp["id"],workshop["id"],other["id"]}


def test_fdp_kpis_cover_active_types_and_server_side_drilldowns(setup):
    client, _, _ = setup
    expected = {"FDP": 1, "STTP": 1, "WORKSHOP": 1, "WEBINAR": 5, "SEMINAR": 1, "INTERNSHIP": 1, "INDUSTRIAL_TRAINING": 1}
    created = {}
    for activity_type, count in expected.items():
        for index in range(count):
            response = client.post("/fdp-activities", json={
                **activity(), "title": f"{activity_type} {index}", "activity_type": activity_type,
                "participants": [{"faculty_id": 1, "role": "ATTENDEE"}, {"faculty_id": 2, "role": "RESOURCE_PERSON"}],
            })
            assert response.status_code == 201
            created.setdefault(activity_type, []).append(response.json()["id"])

    dashboard = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["totals"] == {"activities":11, "faculty_contributors":2, "fdp":1, "sttp":1, "workshops":1, "webinars":5, "seminars":1, "internships":1, "industrial_training":1}
    assert dashboard["types"] == expected
    page = client.get("/fdp-activities?from_date=2026-07-01&to_date=2026-12-31&page=1&page_size=10").json()
    assert page["total"] == 11 and len(page["items"]) == 10
    for activity_type, identities in created.items():
        filtered = client.get(f"/fdp-activities?from_date=2026-07-01&to_date=2026-12-31&faculty_id=1&activity_type={activity_type}&page=1&page_size=10").json()
        assert filtered["total"] == len(identities)
        assert {row["id"] for row in filtered["items"]} == set(identities)

    assert client.delete(f"/fdp-activities/{created['SEMINAR'][0]}").status_code == 200
    active = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert active["totals"]["activities"] == 10 and active["totals"]["seminars"] == 0
    inclusive = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31&include_inactive=true").json()
    assert inclusive["totals"]["activities"] == 11 and inclusive["totals"]["seminars"] == 1
    for retired in ("PROFESSIONAL_TRAINING", "INDUSTRY_COLLABORATION", "OTHER"):
        assert client.post("/fdp-activities", json={**activity(), "title": retired, "activity_type": retired}).status_code == 422


def test_certification_dashboard_overview_filters_and_current_work(setup):
    client, _, _ = setup
    for index in range(11):
        completed=client.post("/certifications",json={
            "faculty_id":1 if index % 2 == 0 else 2,
            "name":f"MOOC {index}",
            "category":"MOOC",
            "provider":"NPTEL",
            "status":"COMPLETED",
            "completion_date":"2026-07-01" if index == 0 else "2026-12-31",
        })
        assert completed.status_code == 201
    for category, name in (("NPTEL_SWAYAM","NPTEL / SWAYAM"),("OTHER","Other")):
        assert client.post("/certifications",json={
            "faculty_id":1,
            "name":name,
            "category":category,
            "provider":"Provider",
            "status":"COMPLETED",
            "completion_date":"2026-08-15",
        }).status_code == 201
    assert client.post("/certifications",json={
        "faculty_id":2,
        "name":"Outside period",
        "category":"MOOC",
        "provider":"NPTEL",
        "status":"COMPLETED",
        "completion_date":"2026-06-30",
    }).status_code == 201
    current=client.post("/certifications",json={
        "faculty_id":2,
        "name":"Current work",
        "category":"MOOC",
        "provider":"NPTEL",
        "status":"IN_PROGRESS",
    }).json()
    inactive=client.post("/certifications",json={
        "faculty_id":2,
        "name":"Inactive other",
        "category":"OTHER",
        "provider":"Provider",
        "status":"COMPLETED",
        "completion_date":"2026-08-15",
    }).json()
    assert client.delete(f"/certifications/{inactive['id']}").status_code == 200

    dashboard=client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["totals"] == {
        "certifications":13,
        "completed":13,
        "in_progress":1,
        "faculty_contributors":2,
    }
    assert dashboard["categories"] == {
        "NPTEL_SWAYAM":1,
        "MOOC":11,
        "OTHER":1,
    }

    filtered=client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31&faculty_id=1&category=MOOC&search=MOOC&status=COMPLETED").json()
    assert filtered["totals"] == {
        "certifications":6,
        "completed":6,
        "in_progress":0,
        "faculty_contributors":1,
    }
    assert filtered["categories"]["MOOC"] == 6

    page=client.get("/certifications?from_date=2026-07-01&to_date=2026-12-31&page=1&page_size=10").json()
    assert page["total"] == 13 and len(page["items"]) == 10
    current_page=client.get("/certifications?from_date=2026-07-01&to_date=2026-12-31&status=IN_PROGRESS&current_in_progress=true&page=1&page_size=10").json()
    assert current_page["total"] == 1 and current_page["items"][0]["id"] == current["id"]
    assert isinstance(client.get("/certifications").json(),list)

    including_inactive=client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31&include_inactive=true").json()
    assert including_inactive["totals"]["completed"] == 14
    assert including_inactive["categories"]["OTHER"] == 2


def test_fdp_optional_fields_editor_parity_and_faculty_participation_summary(setup):
    client, _, _ = setup
    payload={
        **activity(),
        "title":"Complete activity",
        "participants":[
            {"faculty_id":1,"role":"ATTENDEE"},
            {"faculty_id":1,"role":"COORDINATOR"},
            {"faculty_id":2,"role":"RESOURCE_PERSON"},
        ],
        "speakers":[
            {"name":"External One","designation":"Director","organization":"Industry","location_or_contact":"Hyderabad"},
            {"name":"External Two","designation":"Lead","organization":"Institute"},
        ],
        "mode":"HYBRID",
        "location":"Seminar Hall",
        "company_location":"Hyderabad",
        "attendance_count":48,
        "description":"Hands-on FDP",
        "source_url":"https://example.test/fdp",
        "outcomes":"Applied learning",
        "internal_notes":"Coordinator note",
    }
    created=client.post("/fdp-activities",json=payload)
    assert created.status_code == 201
    identity=created.json()["id"]
    detail=client.get(f"/fdp-activities/{identity}").json()
    for key in ("mode","location","company_location","attendance_count","description","source_url","outcomes","internal_notes"):
        assert detail[key] == payload[key]
    assert len(detail["participants"]) == 3 and len(detail["speakers"]) == 2
    assert detail["speakers"][0]["location_or_contact"] == "Hyderabad"
    evidence=client.post(
        f"/fdp-activities/{identity}/evidence",
        data={"evidence_type":"PROGRAM"},
        files={"file":("programme.pdf",b"%PDF-fdp-programme","application/pdf")},
    )
    assert evidence.status_code == 201

    updated={
        **payload,
        "title":"Updated complete activity",
        "mode":"ONLINE",
        "location":"Virtual",
        "participants":[
            {"faculty_id":1,"role":"ATTENDEE"},
            {"faculty_id":1,"role":"COORDINATOR"},
            {"faculty_id":2,"role":"RESOURCE_PERSON"},
        ],
        "speakers":[
            {"name":"Updated external speaker","designation":"Director","organization":"Industry","location_or_contact":"Hyderabad"},
            {"name":"External Two","designation":"Principal lead","organization":"Institute"},
        ],
    }
    response=client.put(f"/fdp-activities/{identity}",json=updated)
    assert response.status_code == 200 and response.json()["id"] == identity
    revised=client.get(f"/fdp-activities/{identity}").json()
    assert revised["title"] == "Updated complete activity"
    assert revised["mode"] == "ONLINE" and revised["location"] == "Virtual"
    assert revised["outcomes"] == payload["outcomes"] and len(revised["speakers"]) == 2
    assert {(row["faculty_id"],row["role"]) for row in revised["participants"]} == {(1,"ATTENDEE"),(1,"COORDINATOR"),(2,"RESOURCE_PERSON")}
    assert revised["speakers"][0]["name"] == "Updated external speaker"
    assert len(client.get(f"/fdp-activities/{identity}/evidence").json()) == 1

    assert client.post("/fdp-activities",json={
        **activity(),
        "title":"Second activity",
        "participants":[{"faculty_id":1,"role":"COORDINATOR"}],
        "speakers":[{"name":"Speaker"}],
    }).status_code == 201
    dashboard=client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    participation={row["id"]:row["activity_count"] for row in dashboard["faculty_participants"]}
    assert dashboard["totals"]["faculty_contributors"] == 2
    assert participation == {1:2,2:1}


def test_faculty_details_certifications_include_current_work_only_for_selected_faculty(setup):
    client, _, _ = setup
    inside=client.post("/certifications",json={
        "faculty_id":1,
        "name":"Completed inside range",
        "category":"MOOC",
        "provider":"NPTEL",
        "status":"COMPLETED",
        "completion_date":"2026-07-01",
    }).json()
    outside=client.post("/certifications",json={
        "faculty_id":1,
        "name":"Completed outside range",
        "category":"MOOC",
        "provider":"NPTEL",
        "status":"COMPLETED",
        "completion_date":"2026-06-30",
    }).json()
    current=client.post("/certifications",json={
        "faculty_id":1,
        "name":"Current faculty work",
        "category":"OTHER",
        "provider":"Provider",
        "status":"IN_PROGRESS",
    }).json()
    other_faculty=client.post("/certifications",json={
        "faculty_id":2,
        "name":"Other Faculty current work",
        "category":"OTHER",
        "provider":"Provider",
        "status":"IN_PROGRESS",
    }).json()
    inactive=client.post("/certifications",json={
        "faculty_id":1,
        "name":"Inactive current work",
        "category":"OTHER",
        "provider":"Provider",
        "status":"IN_PROGRESS",
    }).json()
    assert client.delete(f"/certifications/{inactive['id']}").status_code == 200

    profile=client.get("/research/faculty/1?from_date=2026-07-01&to_date=2026-12-31").json()
    records={row["id"]:row for row in profile["certifications"]}
    assert set(records) == {inside["id"],current["id"]}
    assert records[inside["id"]]["status"] == "COMPLETED"
    assert records[inside["id"]]["publication_date"] == "2026-07-01"
    assert records[current["id"]]["status"] == "IN_PROGRESS"
    assert records[current["id"]]["publication_date"] is None
    assert outside["id"] not in records and inactive["id"] not in records and other_faculty["id"] not in records
    assert {"faculty","summary","publications","patents","books","fdp","certifications","unavailable_modules"} <= set(profile)


def test_historical_faculty_id_is_preserved_for_fdp_and_certifications(setup):
    client, factory, _ = setup
    from backend.models import Faculty

    with factory() as db:
        db.add(Faculty(id=3,employee_id="H",name="Historical Faculty",name_variants=[],is_active=False))
        db.commit()

    activity_response=client.post("/fdp-activities",json={
        **activity(),
        "participants":[{"faculty_id":3,"role":"ATTENDEE"}],
    })
    assert activity_response.status_code == 201
    activity_record=activity_response.json()
    assert activity_record["participants"][0]["faculty_id"] == 3
    activities_response=client.get("/fdp-activities?faculty_id=3")
    assert activities_response.status_code == 200
    assert activities_response.json()[0]["id"] == activity_record["id"]

    certification_response=client.post("/certifications",json={
        "faculty_id":3,
        "name":"Historical Faculty Credential",
        "category":"MOOC",
        "provider":"NPTEL",
        "status":"COMPLETED",
        "completion_date":"2026-08-01",
    })
    assert certification_response.status_code == 201
    certification=certification_response.json()
    updated={**certification,"provider":"Updated NPTEL"}
    update_response=client.put(f"/certifications/{certification['id']}",json=updated)
    assert update_response.status_code == 200
    saved=update_response.json()
    assert saved["id"] == certification["id"] and saved["faculty_id"] == 3
    certifications_response=client.get("/certifications?faculty_id=3")
    assert certifications_response.status_code == 200
    assert certifications_response.json()[0]["id"] == certification["id"]


def test_fdp_and_certification_dashboard_analytics_are_full_filtered_sets(setup):
    client, _, _ = setup
    first = client.post("/fdp-activities", json={
        **activity(), "participants": [
            {"faculty_id": 1, "role": "ATTENDEE"}, {"faculty_id": 1, "role": "COORDINATOR"},
            {"faculty_id": 2, "role": "RESOURCE_PERSON"},
        ],
    })
    second = client.post("/fdp-activities", json={
        **activity(), "title": "Workshop analytics", "activity_type": "WORKSHOP",
        "participants": [{"faculty_id": 1, "role": "ATTENDEE"}], "speakers": [{"name": "External"}],
    })
    assert first.status_code == 201 and second.status_code == 201
    fdp = client.get("/fdp-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert fdp["types"]["FDP"] == 1 and fdp["types"]["WORKSHOP"] == 1
    assert fdp["role_counts"]["ATTENDEE"] == 2 and fdp["role_counts"]["COORDINATOR"] == 1
    faculty = {row["id"]: row for row in fdp["faculty_performance"]}
    assert faculty[1]["activities"] == 2 and faculty[1]["participations"] == 3
    assert next(row for row in fdp["trend"] if row["month"] == "2026-08")["activities"] == 2

    for category, provider in (("MOOC", "NPTEL"), ("OTHER", "Coursera")):
        assert client.post("/certifications", json={
            "faculty_id": 1, "name": category, "category": category, "provider": provider,
            "status": "COMPLETED", "completion_date": "2026-08-01",
        }).status_code == 201
    assert client.post("/certifications", json={
        "faculty_id": 2, "name": "Current", "category": "OTHER", "provider": "NPTEL", "status": "IN_PROGRESS",
    }).status_code == 201
    certifications = client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert certifications["categories"] == {"NPTEL_SWAYAM": 0, "MOOC": 1, "OTHER": 1}
    assert certifications["providers"][0] == {"provider": "Coursera", "completed": 1}
    performance = {row["id"]: row for row in certifications["faculty_performance"]}
    assert performance[1]["completed"] == 2 and performance[2]["in_progress"] == 1
    assert next(row for row in certifications["trend"] if row["month"] == "2026-08")["completed"] == 2


def test_fdp_faculty_participated_kpi_uses_distinct_faculty_and_dashboard_scope(setup):
    client, factory, _ = setup
    from backend.models import Faculty

    with factory() as db:
        db.add(Faculty(id=3, employee_id="C", name="Faculty C", name_variants=[]))
        db.commit()

    first = client.post("/fdp-activities", json={
        **activity(), "title": "FDP participation", "participants": [
            {"faculty_id": 1, "role": "ATTENDEE"},
            {"faculty_id": 1, "role": "COORDINATOR"},
            {"faculty_id": 2, "role": "RESOURCE_PERSON"},
        ],
    })
    workshop = client.post("/fdp-activities", json={
        **activity(), "title": "Workshop participation", "activity_type": "WORKSHOP", "participants": [
            {"faculty_id": 1, "role": "ATTENDEE"}, {"faculty_id": 3, "role": "COORDINATOR"},
        ],
    })
    inactive = client.post("/fdp-activities", json={
        **activity(), "title": "Inactive webinar", "activity_type": "WEBINAR", "participants": [{"faculty_id": 3, "role": "ATTENDEE"}],
    })
    outside_period = client.post("/fdp-activities", json={
        **activity(), "title": "Outside period", "start_date": "2027-01-01", "end_date": "2027-01-02",
        "participants": [{"faculty_id": 3, "role": "ATTENDEE"}],
    })
    assert first.status_code == workshop.status_code == inactive.status_code == outside_period.status_code == 201
    assert client.delete(f"/fdp-activities/{inactive.json()['id']}").status_code == 200

    period = "from_date=2026-07-01&to_date=2026-12-31"
    dashboard = client.get("/fdp-dashboard?" + period).json()
    participants = {row["id"]: row for row in dashboard["faculty_participants"]}
    assert dashboard["totals"]["faculty_contributors"] == len(participants) == 3
    assert participants[1]["activity_count"] == 2 and participants[1]["roles"] == ["ATTENDEE", "COORDINATOR"]
    assert participants[2]["activity_count"] == participants[3]["activity_count"] == 1
    assert dashboard["types"] == {"FDP": 1, "STTP": 0, "WORKSHOP": 1, "WEBINAR": 0, "SEMINAR": 0, "INTERNSHIP": 0, "INDUSTRIAL_TRAINING": 0}

    faculty_filtered = client.get("/fdp-dashboard?" + period + "&faculty_id=1").json()
    role_filtered = client.get("/fdp-dashboard?" + period + "&role=COORDINATOR").json()
    type_filtered = client.get("/fdp-dashboard?" + period + "&activity_type=FDP").json()
    paged_dashboard = client.get("/fdp-dashboard?" + period + "&page=2&page_size=10").json()
    assert faculty_filtered["totals"]["faculty_contributors"] == 1
    assert role_filtered["totals"]["faculty_contributors"] == 2
    assert type_filtered["totals"]["faculty_contributors"] == 2
    assert paged_dashboard == dashboard
    assert [row["id"] for row in faculty_filtered["faculty_participants"]] == [1]
    assert {row["id"] for row in role_filtered["faculty_participants"]} == {1, 3}
    assert all(row["roles"] == ["COORDINATOR"] for row in role_filtered["faculty_participants"])
    assert {row["id"] for row in type_filtered["faculty_participants"]} == {1, 2}

    faculty_records = client.get("/fdp-activities?" + period + "&faculty_id=1&page=1&page_size=all").json()
    coordinator_records = client.get("/fdp-activities?" + period + "&faculty_id=1&role=COORDINATOR&page=1&page_size=all").json()
    attendee_records = client.get("/fdp-activities?" + period + "&faculty_id=1&role=ATTENDEE&page=1&page_size=all").json()
    faculty_three_coordinator = client.get("/fdp-activities?" + period + "&faculty_id=3&role=COORDINATOR&page=1&page_size=all").json()
    faculty_two_resource_person = client.get("/fdp-activities?" + period + "&faculty_id=2&role=RESOURCE_PERSON&page=1&page_size=all").json()
    faculty_one_resource_person = client.get("/fdp-activities?" + period + "&faculty_id=1&role=RESOURCE_PERSON&page=1&page_size=all").json()
    all_coordinators = client.get("/fdp-activities?" + period + "&role=COORDINATOR&page=1&page_size=all").json()
    first_page = client.get("/fdp-activities?" + period + "&faculty_id=1&role=ATTENDEE&page=1&page_size=10").json()
    page_size_twenty_five = client.get("/fdp-activities?" + period + "&faculty_id=1&role=ATTENDEE&page=1&page_size=25").json()
    page_size_fifty = client.get("/fdp-activities?" + period + "&faculty_id=1&role=ATTENDEE&page=1&page_size=50").json()
    assert {row["id"] for row in faculty_records["items"]} == {first.json()["id"], workshop.json()["id"]}
    assert [row["id"] for row in coordinator_records["items"]] == [first.json()["id"]]
    assert {row["id"] for row in attendee_records["items"]} == {first.json()["id"], workshop.json()["id"]}
    assert [row["id"] for row in faculty_three_coordinator["items"]] == [workshop.json()["id"]]
    assert [row["id"] for row in faculty_two_resource_person["items"]] == [first.json()["id"]]
    assert faculty_one_resource_person["total"] == 0 and faculty_one_resource_person["items"] == []
    assert {row["id"] for row in all_coordinators["items"]} == {first.json()["id"], workshop.json()["id"]}
    assert first_page["total"] == 2 and {row["id"] for row in first_page["items"]} == {first.json()["id"], workshop.json()["id"]}
    assert page_size_twenty_five["total"] == page_size_fifty["total"] == 2
    assert {row["id"] for row in page_size_twenty_five["items"]} == {row["id"] for row in page_size_fifty["items"]} == {first.json()["id"], workshop.json()["id"]}


def test_certification_approved_categories_are_filterable_and_legacy_value_is_rejected(setup):
    client, _, _ = setup
    rows = {}
    for category, faculty_id in (("NPTEL_SWAYAM", 1), ("MOOC", 2), ("OTHER", 1)):
        response = client.post("/certifications", json={
            "faculty_id": faculty_id, "name": category, "category": category,
            "provider": "Provider", "status": "COMPLETED", "completion_date": "2026-08-01",
        })
        assert response.status_code == 201
        rows[category] = response.json()
    dashboard = client.get("/certification-dashboard?from_date=2026-07-01&to_date=2026-12-31").json()
    assert dashboard["categories"] == {"NPTEL_SWAYAM": 1, "MOOC": 1, "OTHER": 1}
    for category, row in rows.items():
        filtered = client.get(f"/certifications?category={category}")
        assert filtered.status_code == 200 and [item["id"] for item in filtered.json()] == [row["id"]]
    updated = client.put(f"/certifications/{rows['NPTEL_SWAYAM']['id']}", json={**rows["NPTEL_SWAYAM"], "provider": "Updated Provider"})
    assert updated.status_code == 200 and updated.json()["id"] == rows["NPTEL_SWAYAM"]["id"]
    assert client.post("/certifications", json={**rows["MOOC"], "id": None, "name": "Legacy", "category": "PROFESSIONAL_CERTIFICATION"}).status_code == 422
