"""Acceptance checks for shared institutional Department reporting semantics."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from backend.department_filtering import eligible_department_record_ids
from backend.models import Department, Faculty, FacultyDepartmentAffiliation, FundingProject, FundingProjectFaculty
from backend.scoped_reporting import scoped_overview


def _faculty(identity, department_id, start, end=None):
    person = Faculty(id=identity, employee_id=f"IR-{identity}", name=f"Faculty {identity}", name_variants=[])
    person.department_affiliations = [FacultyDepartmentAffiliation(
        department_id=department_id, effective_from=start, effective_to=end,
        is_primary=True, source="MANUAL_TRANSFER",
    )]
    return person


def test_funding_predicate_and_scoped_overview_preserve_shared_project_semantics(setup):
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        db.add(cse); db.flush()
        first = _faculty(701, eee.id, date(2025, 7, 1))
        second = _faculty(702, cse.id, date(2025, 7, 1))
        db.add_all([first, second]); db.flush()
        project = FundingProject(
            title="Shared institutional project", category="SPONSORED_RESEARCH",
            department="Recorded EEE", status="SANCTIONED", sanction_date=date(2026, 9, 1),
            sanctioned_amount=Decimal("2000000.00"),
        )
        project.faculty = [
            FundingProjectFaculty(faculty_id=701, role="LEAD_PI", affiliation_type="FACULTY_MASTER"),
            FundingProjectFaculty(faculty_id=702, role="CO_PI", affiliation_type="FACULTY_MASTER"),
        ]
        db.add(project); db.commit()
        project_id, eee_id, cse_id = project.id, eee.id, cse.id

        for department_id in (eee_id, cse_id):
            predicate_ids = db.scalars(select(FundingProject.id).where(
                FundingProject.id.in_(eligible_department_record_ids(db, "funding", department_id))
            )).all()
            assert predicate_ids == [project_id]
            scoped = scoped_overview(
                db, start=date(2026, 7, 1), end=date(2026, 12, 31),
                scope="DEPARTMENT", department_id=department_id,
            )
            assert scoped["totals"]["research_projects"] == 1

        institution = scoped_overview(db, start=date(2026, 7, 1), end=date(2026, 12, 31))
        assert institution["totals"]["research_projects"] == 1

    period = "from_date=2026-07-01&to_date=2026-12-31&category=SPONSORED_RESEARCH"
    for department_id in (eee_id, cse_id):
        response = client.get(f"/funding-dashboard?{period}&department_id={department_id}")
        assert response.status_code == 200, response.text
        assert response.json()["totals"]["total"] == 1
        assert response.json()["totals"]["sanctioned_amount"] == 2000000


def test_funding_activity_date_requires_the_same_project_sanction_date(setup):
    _, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        faculty = _faculty(703, eee.id, date(2025, 7, 1))
        db.add(faculty); db.flush()
        dated = FundingProject(title="Dated", category="SPONSORED_RESEARCH", department="EEE", status="SANCTIONED", sanction_date=date(2026, 9, 1))
        dated.faculty = [FundingProjectFaculty(faculty_id=703, role="LEAD_PI", affiliation_type="FACULTY_MASTER")]
        undated = FundingProject(title="Undated proposal", category="SPONSORED_RESEARCH", department="EEE", status="DRAFT", proposal_submission_date=date(2026, 9, 2))
        undated.faculty = [FundingProjectFaculty(faculty_id=703, role="MEMBER_PI", affiliation_type="FACULTY_MASTER")]
        db.add_all([dated, undated]); db.commit()
        ids = db.scalars(select(FundingProject.id).where(FundingProject.id.in_(
            eligible_department_record_ids(db, "funding", eee.id, attribution_mode="AT_ACTIVITY_DATE")
        )).order_by(FundingProject.id)).all()
        assert ids == [dated.id]


def test_legacy_research_overview_remains_callable_after_department_filtering(setup):
    client, _, _ = setup
    response = client.get("/research/overview?from_date=2026-07-01&to_date=2026-12-31")
    assert response.status_code == 200, response.text
