from conftest import paper


def test_unused_faculty_student_and_academic_year_can_be_deleted(setup):
    client, _, _ = setup
    faculty = client.post("/faculty", json={"employee_id": "UNUSED-F", "name": "Unused Faculty"})
    student = client.post("/students", json={"roll_number": "UNUSED-S", "name": "Unused Student"})
    year = client.post("/academic-years", json={
        "name": "2030-31", "start_date": "2030-07-01", "end_date": "2031-06-30",
    })
    assert faculty.status_code == student.status_code == year.status_code == 201

    for path, response in (("/faculty", faculty), ("/students", student), ("/academic-years", year)):
        deleted = client.delete(f"{path}/{response.json()['id']}")
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] == response.json()["id"]
        assert client.delete(f"{path}/{response.json()['id']}").status_code == 404


def test_referenced_masters_are_protected_with_dependency_messages(setup):
    client, _, _ = setup
    payload = paper("10.1234/master-delete")
    payload["academic_year_id"] = 1
    created = client.post("/publications", json=payload)
    assert created.status_code == 201, created.text

    faculty = client.delete("/faculty/1")
    student = client.delete("/students/1")
    year = client.delete("/academic-years/1")
    for response, expected in ((faculty, "publication author associations"), (student, "publication author associations"), (year, "publications")):
        assert response.status_code == 409, response.text
        assert expected in response.json()["detail"]

    assert client.get("/publications/1").status_code == 200


def test_master_delete_does_not_cascade_to_unrelated_records(setup):
    client, _, _ = setup
    unused = client.post("/faculty", json={"employee_id": "ISOLATED", "name": "Isolated Faculty"})
    publication = client.post("/publications", json=paper("10.1234/no-cascade"))
    assert unused.status_code == publication.status_code == 201

    assert client.delete(f"/faculty/{unused.json()['id']}").status_code == 200
    detail = client.get(f"/publications/{publication.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["authors"][0]["faculty_id"] == 1
