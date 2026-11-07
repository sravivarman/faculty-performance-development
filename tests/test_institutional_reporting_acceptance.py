"""Final institutional-reporting acceptance checks.

The specialised module suites retain their detailed CRUD coverage.  These
checks exercise the cross-module reporting contract: a shared parent record is
one institutional record, can appear once per eligible Department, and can be
credited to a Faculty profile only through that Faculty's own association.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from backend.models import (
    BookContributor,
    BookPublication,
    Certification,
    Department,
    Faculty,
    FacultyDepartmentAffiliation,
    FdpActivity,
    FdpParticipant,
    FundingProject,
    FundingProjectFaculty,
    Patent,
    PatentInventor,
    Publication,
    PublicationAuthor,
)
from backend.scoped_reporting import scoped_overview


PERIOD = "from_date=2026-07-01&to_date=2026-12-31"


def _faculty(identity, department_id, start=date(2025, 7, 1), end=None, *, active=True):
    person = Faculty(id=identity, employee_id=f"IRA-{identity}", name=f"Faculty {identity}", name_variants=[], is_active=active)
    person.department_affiliations = [FacultyDepartmentAffiliation(
        department_id=department_id, effective_from=start, effective_to=end,
        is_primary=True, source="MANUAL_TRANSFER",
    )]
    return person


def test_shared_records_reconcile_across_institution_department_and_faculty_scopes(setup):
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        db.add(cse); db.flush()
        left = _faculty(901, eee.id, active=False)
        right = _faculty(902, cse.id)
        db.add_all([left, right]); db.flush()

        publication = Publication(title="Shared acceptance publication", publication_type="JOURNAL", publication_date=date(2026, 9, 1), indexing=[], classification="UNKNOWN")
        publication.authors = [
            PublicationAuthor(author_order=1, author_name_from_source="Faculty 901", person_type="FACULTY", faculty_id=901, is_internal=True, is_claiming_faculty=True),
            PublicationAuthor(author_order=2, author_name_from_source="Faculty 902", person_type="FACULTY", faculty_id=902, is_internal=True),
        ]
        patent = Patent(title="Shared acceptance patent", patent_office="IPO", current_status="FILED", filing_date=date(2026, 9, 1))
        patent.inventors = [
            PatentInventor(inventor_order=1, inventor_name="Faculty 901", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=901, is_claiming_faculty=True),
            PatentInventor(inventor_order=2, inventor_name="Faculty 902", person_type="FACULTY", institution_scope="SAME_INSTITUTION_OTHER_DEPARTMENT", faculty_id=902),
        ]
        book = BookPublication(work_type="BOOK", title="Shared acceptance book", publisher="VCE", publication_date=date(2026, 9, 1))
        book.contributors = [
            BookContributor(contributor_order=1, contributor_name="Faculty 901", role="AUTHOR", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=901, is_claiming_faculty=True),
            BookContributor(contributor_order=2, contributor_name="Faculty 902", role="AUTHOR", person_type="FACULTY", institution_scope="SAME_INSTITUTION_OTHER_DEPARTMENT", faculty_id=902),
        ]
        activity = FdpActivity(title="Shared acceptance FDP", activity_type="FDP", organizing_institution="VCE", start_date=date(2026, 9, 1), duration_value=1, duration_unit="DAYS")
        activity.participants = [FdpParticipant(faculty_id=901, role="ATTENDEE"), FdpParticipant(faculty_id=902, role="COORDINATOR")]
        certification = Certification(faculty_id=901, name="Acceptance credential", category="MOOC", provider="Provider", status="COMPLETED", completion_date=date(2026, 9, 1))
        project = FundingProject(title="Shared acceptance project", category="SPONSORED_RESEARCH", department="Recorded EEE", status="SANCTIONED", sanction_date=date(2026, 9, 1), sanctioned_amount=Decimal("2000000.00"))
        project.faculty = [
            FundingProjectFaculty(faculty_id=901, role="LEAD_PI", affiliation_type="FACULTY_MASTER"),
            FundingProjectFaculty(faculty_id=902, role="CO_PI", affiliation_type="FACULTY_MASTER"),
        ]
        db.add_all([publication, patent, book, activity, certification, project]); db.commit()

        institution = scoped_overview(db, start=date(2026, 7, 1), end=date(2026, 12, 31))
        eee_scope = scoped_overview(db, start=date(2026, 7, 1), end=date(2026, 12, 31), scope="DEPARTMENT", department_id=eee.id)
        cse_scope = scoped_overview(db, start=date(2026, 7, 1), end=date(2026, 12, 31), scope="DEPARTMENT", department_id=cse.id)

    assert institution["totals"]["publications"] == institution["totals"]["patents"] == institution["totals"]["books"] == institution["totals"]["fdp"] == 1
    assert institution["totals"]["research_projects"] == 1
    assert eee_scope["totals"]["publications"] == cse_scope["totals"]["publications"] == 1
    assert eee_scope["totals"]["research_projects"] == cse_scope["totals"]["research_projects"] == 1

    complete = client.get(f"/research/faculty/901?{PERIOD}")
    assert complete.status_code == 200, complete.text
    assert complete.json()["faculty"]["is_active"] is False
    assert complete.json()["summary"]["publications_claimed"] == 1
    assert complete.json()["summary"]["patents"] == complete.json()["summary"]["books"] == complete.json()["summary"]["fdp"] == 1

    wrong = client.get(f"/research/faculty/901?{PERIOD}&department_id={cse.id}&attribution_mode=CURRENT")
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["summary"]["publications_authored"] == 0
    assert wrong.json()["summary"]["patents"] == wrong.json()["summary"]["books"] == wrong.json()["summary"]["fdp"] == 0
    assert wrong.json()["summary"]["funding_projects"] == 0


def test_funding_dashboard_sums_distinct_projects_not_distinct_amount_values(setup):
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        lead = _faculty(903, eee.id)
        colleague = _faculty(904, eee.id)
        db.add_all([lead, colleague]); db.flush()
        for title in ("First identical amount project", "Second identical amount project"):
            project = FundingProject(title=title, category="SPONSORED_RESEARCH", department="Recorded EEE", status="SANCTIONED", sanction_date=date(2026, 9, 1), sanctioned_amount=Decimal("1000000.00"))
            project.faculty = [
                FundingProjectFaculty(faculty_id=903, role="LEAD_PI", affiliation_type="FACULTY_MASTER"),
                FundingProjectFaculty(faculty_id=904, role="CO_PI", affiliation_type="FACULTY_MASTER"),
            ]
            db.add(project)
        db.commit()

    response = client.get(f"/funding-dashboard?{PERIOD}&category=SPONSORED_RESEARCH&department_id={eee.id}")
    assert response.status_code == 200, response.text
    assert response.json()["totals"]["total"] == 2
    assert response.json()["totals"]["sanctioned_amount"] == 2000000
