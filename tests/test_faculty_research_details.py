"""Focused Faculty-profile scope checks.

These tests deliberately use a shared parent record with contributors from two
Departments.  They guard against using the record-level Department inventory
predicate for a selected Faculty profile.
"""
from datetime import date

from sqlalchemy import select

from backend.models import (
    Department,
    Faculty,
    FacultyDepartmentAffiliation,
    FdpActivity,
    FdpParticipant,
    FundingProject,
    FundingProjectFaculty,
    Publication,
    PublicationAuthor,
)


def faculty(identity, name, department_id, start=date(2025, 7, 1), end=None):
    result = Faculty(id=identity, employee_id=f"FRD-{identity}", name=name, name_variants=[])
    result.department_affiliations = [FacultyDepartmentAffiliation(
        department_id=department_id,
        effective_from=start,
        effective_to=end,
        is_primary=True,
        source="MANUAL_TRANSFER",
    )]
    return result


def profile(client, identity, extra=""):
    query = "from_date=2026-07-01&to_date=2026-12-31"
    return client.get(f"/research/faculty/{identity}?{query}{extra}")


def test_complete_and_department_faculty_profiles_keep_the_selected_contributor(setup):
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        db.add(cse); db.flush()
        first = faculty(801, "EEE Faculty", eee.id)
        second = faculty(802, "CSE Faculty", cse.id)
        db.add_all([first, second]); db.flush()

        publication = Publication(title="Shared profile publication", publication_type="JOURNAL", publication_date=date(2026, 9, 1), indexing=[], classification="UNKNOWN")
        publication.authors = [
            PublicationAuthor(author_order=1, author_name_from_source="EEE Faculty", person_type="FACULTY", faculty_id=801, is_internal=True, is_claiming_faculty=True),
            PublicationAuthor(author_order=2, author_name_from_source="CSE Faculty", person_type="FACULTY", faculty_id=802, is_internal=True),
        ]
        activity = FdpActivity(title="Shared FDP", activity_type="FDP", organizing_institution="VCE", start_date=date(2026, 9, 1), duration_value=1, duration_unit="DAYS")
        activity.participants = [FdpParticipant(faculty_id=801, role="ATTENDEE"), FdpParticipant(faculty_id=802, role="COORDINATOR")]
        project = FundingProject(title="Shared project", category="SPONSORED_RESEARCH", department="Recorded EEE", status="SANCTIONED", sanction_date=date(2026, 9, 1))
        project.faculty = [FundingProjectFaculty(faculty_id=801, role="LEAD_PI", affiliation_type="FACULTY_MASTER"), FundingProjectFaculty(faculty_id=802, role="CO_PI", affiliation_type="FACULTY_MASTER")]
        db.add_all([publication, activity, project]); db.commit()

    complete = profile(client, 801)
    assert complete.status_code == 200, complete.text
    assert complete.json()["context"]["type"] == "COMPLETE_PROFILE"
    assert complete.json()["summary"]["publications_authored"] == 1
    assert complete.json()["summary"]["fdp"] == 1
    assert complete.json()["summary"]["funding_projects"] == 1

    wrong_department = profile(client, 801, f"&department_id={cse.id}&attribution_mode=CURRENT")
    assert wrong_department.status_code == 200, wrong_department.text
    payload = wrong_department.json()
    assert payload["context"]["type"] == "DEPARTMENT_ATTRIBUTED"
    assert payload["summary"]["publications_authored"] == 0
    assert payload["summary"]["fdp"] == 0
    assert payload["summary"]["funding_projects"] == 0

    matching_department = profile(client, 801, f"&department_id={eee.id}&attribution_mode=CURRENT")
    assert matching_department.status_code == 200, matching_department.text
    assert matching_department.json()["summary"]["publications_claimed"] == 1
    assert matching_department.json()["fdp"][0]["roles"] == ["ATTENDEE"]
    assert matching_department.json()["funding_projects"][0]["roles"] == ["LEAD_PI"]


def test_activity_date_scope_uses_verified_history_and_validates_department(setup):
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        db.add(cse); db.flush()
        moved = faculty(803, "Transferred Faculty", eee.id, date(2025, 7, 1), date(2026, 8, 31))
        moved.department_affiliations.append(FacultyDepartmentAffiliation(
            department_id=cse.id, effective_from=date(2026, 9, 1), effective_to=None,
            is_primary=True, source="MANUAL_TRANSFER",
        ))
        db.add(moved); db.flush()
        before = Publication(title="Before transfer", publication_type="JOURNAL", publication_date=date(2026, 8, 1), indexing=[], classification="UNKNOWN")
        before.authors = [PublicationAuthor(author_order=1, author_name_from_source="Moved", person_type="FACULTY", faculty_id=803, is_internal=True, is_claiming_faculty=True)]
        after = Publication(title="After transfer", publication_type="JOURNAL", publication_date=date(2026, 10, 1), indexing=[], classification="UNKNOWN")
        after.authors = [PublicationAuthor(author_order=1, author_name_from_source="Moved", person_type="FACULTY", faculty_id=803, is_internal=True, is_claiming_faculty=True)]
        db.add_all([before, after]); db.commit()

    historical_eee = profile(client, 803, f"&department_id={eee.id}&attribution_mode=AT_ACTIVITY_DATE")
    assert historical_eee.status_code == 200, historical_eee.text
    assert [row["title"] for row in historical_eee.json()["publications"]] == ["Before transfer"]
    historical_cse = profile(client, 803, f"&department_id={cse.id}&attribution_mode=AT_ACTIVITY_DATE")
    assert historical_cse.status_code == 200, historical_cse.text
    assert [row["title"] for row in historical_cse.json()["publications"]] == ["After transfer"]

    assert profile(client, 803, "&department_id=999999").status_code == 422
    assert profile(client, 803, "&attribution_mode=NOT_A_MODE").status_code == 422
