"""Focused SQL-composition tests for the Phase 3D.1 Department helper."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from backend.department_filtering import eligible_department_record_ids
from backend.models import (
    BookContributor, BookPublication, Certification, Department, Faculty,
    FacultyDepartmentAffiliation, FdpActivity, FdpParticipant, FundingProject,
    FundingProjectFaculty, Patent, PatentInventor, Publication, PublicationAuthor,
)


def _faculty(identity, name, department_id, start=date(2025, 7, 1), end=None):
    person = Faculty(id=identity, employee_id=f"DF-{identity}", name=name, name_variants=[])
    person.department_affiliations = [FacultyDepartmentAffiliation(
        department_id=department_id, effective_from=start, effective_to=end,
        is_primary=True, source="MANUAL_TRANSFER",
    )]
    return person


def _ids(db, model, module, department_id, mode="CURRENT"):
    statement = eligible_department_record_ids(db, module, department_id, attribution_mode=mode)
    return db.scalars(select(model.id).where(model.id.in_(statement)).order_by(model.id)).all()


def test_department_helper_composes_distinct_parent_ids_for_every_supported_module(setup):
    _, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        db.add(cse); db.flush()
        first = _faculty(101, "EEE Faculty A", eee.id)
        second = _faculty(102, "EEE Faculty B", eee.id)
        third = _faculty(103, "CSE Faculty", cse.id)
        db.add_all([first, second, third]); db.flush()

        publication = Publication(title="Shared publication", publication_type="JOURNAL", publication_date=date(2026, 9, 1), indexing=[], classification="UNKNOWN")
        publication.authors = [
            PublicationAuthor(author_order=1, author_name_from_source="EEE A", person_type="FACULTY", faculty_id=101, is_internal=True, is_claiming_faculty=True),
            PublicationAuthor(author_order=2, author_name_from_source="EEE B", person_type="FACULTY", faculty_id=102, is_internal=True),
            PublicationAuthor(author_order=3, author_name_from_source="CSE", person_type="FACULTY", faculty_id=103, is_internal=True),
        ]
        patent = Patent(title="Shared patent", patent_office="IPO", current_status="FILED", filing_date=date(2026, 9, 1))
        patent.inventors = [
            PatentInventor(inventor_order=1, inventor_name="EEE A", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=101, is_claiming_faculty=True),
            PatentInventor(inventor_order=2, inventor_name="CSE", person_type="FACULTY", institution_scope="SAME_INSTITUTION_OTHER_DEPARTMENT", faculty_id=103),
        ]
        book = BookPublication(work_type="BOOK", title="Shared book", publisher="VCE", publication_date=date(2026, 9, 1))
        book.contributors = [
            BookContributor(contributor_order=1, contributor_name="EEE A", role="AUTHOR", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=101, is_claiming_faculty=True),
            BookContributor(contributor_order=2, contributor_name="CSE", role="AUTHOR", person_type="FACULTY", institution_scope="SAME_INSTITUTION_OTHER_DEPARTMENT", faculty_id=103),
        ]
        activity = FdpActivity(title="Shared FDP", activity_type="FDP", organizing_institution="VCE", start_date=date(2026, 9, 1), duration_value=1, duration_unit="DAYS")
        activity.participants = [FdpParticipant(faculty_id=101, role="ATTENDEE"), FdpParticipant(faculty_id=103, role="COORDINATOR")]
        certification = Certification(faculty_id=103, name="CSE credential", category="MOOC", provider="Provider", status="COMPLETED", completion_date=date(2026, 9, 1))
        project = FundingProject(title="Shared project", category="SPONSORED_RESEARCH", department="Recorded EEE", status="SANCTIONED", sanction_date=date(2026, 9, 1))
        project.faculty = [FundingProjectFaculty(faculty_id=101, role="MEMBER_PI", affiliation_type="FACULTY_MASTER"), FundingProjectFaculty(faculty_id=103, role="CO_PI", affiliation_type="FACULTY_MASTER")]
        db.add_all([publication, patent, book, activity, certification, project]); db.commit()

        assert _ids(db, Publication, "publications", eee.id) == [publication.id]
        assert _ids(db, Publication, "publications", cse.id) == [publication.id]
        assert _ids(db, Patent, "patents", eee.id) == [patent.id]
        assert _ids(db, Patent, "patents", cse.id) == [patent.id]
        assert _ids(db, BookPublication, "books", eee.id) == [book.id]
        assert _ids(db, FdpActivity, "fdp", cse.id) == [activity.id]
        assert _ids(db, Certification, "certifications", cse.id) == [certification.id]
        assert _ids(db, FundingProject, "funding", eee.id) == [project.id]
        assert _ids(db, FundingProject, "funding", cse.id) == [project.id]


def test_activity_date_attribution_requires_verified_interval_and_preserves_current_mode(setup):
    _, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        db.add(cse); db.flush()
        transferred = _faculty(104, "Transferred Faculty", eee.id, date(2025, 7, 1), date(2026, 12, 31))
        transferred.department_affiliations.append(FacultyDepartmentAffiliation(
            department_id=cse.id, effective_from=date(2027, 1, 1), effective_to=None,
            is_primary=True, source="MANUAL_TRANSFER",
        ))
        legacy = Faculty(id=105, employee_id="DF-105", name="Legacy Faculty", name_variants=[])
        legacy.department_affiliations = [FacultyDepartmentAffiliation(
            department_id=eee.id, effective_from=None, effective_to=None,
            is_primary=True, source="MIGRATION_BASELINE",
        )]
        db.add_all([transferred, legacy]); db.flush()
        before = Publication(title="Before transfer", publication_type="JOURNAL", publication_date=date(2026, 9, 1), indexing=[], classification="UNKNOWN")
        before.authors = [PublicationAuthor(author_order=1, author_name_from_source="Transferred", person_type="FACULTY", faculty_id=104, is_internal=True, is_claiming_faculty=True)]
        old = Publication(title="Legacy history", publication_type="JOURNAL", publication_date=date(2020, 9, 1), indexing=[], classification="UNKNOWN")
        old.authors = [PublicationAuthor(author_order=1, author_name_from_source="Legacy", person_type="FACULTY", faculty_id=105, is_internal=True, is_claiming_faculty=True)]
        activity = FdpActivity(title="Verified historical FDP", activity_type="FDP", organizing_institution="VCE", start_date=date(2026, 9, 1), duration_value=1, duration_unit="DAYS")
        activity.participants = [FdpParticipant(faculty_id=104, role="ATTENDEE")]
        legacy_activity = FdpActivity(title="Unverified legacy FDP", activity_type="FDP", organizing_institution="VCE", start_date=date(2020, 9, 1), duration_value=1, duration_unit="DAYS")
        legacy_activity.participants = [FdpParticipant(faculty_id=105, role="ATTENDEE")]
        certification = Certification(faculty_id=104, name="Verified historical certification", category="MOOC", provider="Provider", status="COMPLETED", completion_date=date(2026, 9, 1))
        legacy_certification = Certification(faculty_id=105, name="Unverified legacy certification", category="MOOC", provider="Provider", status="COMPLETED", completion_date=date(2020, 9, 1))
        db.add_all([before, old, activity, legacy_activity, certification, legacy_certification]); db.commit()

        assert _ids(db, Publication, "publications", eee.id, "AT_ACTIVITY_DATE") == [before.id]
        assert _ids(db, Publication, "publications", cse.id, "AT_ACTIVITY_DATE") == []
        assert _ids(db, Publication, "publications", cse.id, "CURRENT") == [before.id]
        assert old.id not in _ids(db, Publication, "publications", eee.id, "AT_ACTIVITY_DATE")
        assert _ids(db, FdpActivity, "fdp", eee.id, "AT_ACTIVITY_DATE") == [activity.id]
        assert _ids(db, FdpActivity, "fdp", cse.id, "AT_ACTIVITY_DATE") == []
        assert legacy_activity.id not in _ids(db, FdpActivity, "fdp", eee.id, "AT_ACTIVITY_DATE")
        assert _ids(db, Certification, "certifications", eee.id, "AT_ACTIVITY_DATE") == [certification.id]
        assert legacy_certification.id not in _ids(db, Certification, "certifications", eee.id, "AT_ACTIVITY_DATE")


def test_publication_api_department_filter_applies_before_dashboard_counts_and_pagination(setup):
    client, _, _ = setup
    eee = next(item for item in client.get("/departments").json() if item["code"] == "EEE")
    cse = client.post("/departments", json={"code": "CSE", "name": "Computer Science and Engineering"}).json()
    first = client.post("/faculty", json={"employee_id": "DFP-EEE-A", "name": "EEE A", "department_id": eee["id"], "department_effective_from": "2025-07-01"}).json()
    second = client.post("/faculty", json={"employee_id": "DFP-EEE-B", "name": "EEE B", "department_id": eee["id"], "department_effective_from": "2025-07-01"}).json()
    third = client.post("/faculty", json={"employee_id": "DFP-CSE", "name": "CSE C", "department_id": cse["id"], "department_effective_from": "2025-07-01"}).json()
    response = client.post("/publications", json={
        "doi": "10.1234/department-api", "title": "Shared Department Publication", "publication_type": "JOURNAL",
        "journal_conference_name": "VCE Journal", "publication_date": "2026-09-01", "indexing": ["SCOPUS"],
        "authors": [
            {"author_order": 1, "author_name_from_source": "EEE A", "person_type": "FACULTY", "faculty_id": first["id"], "is_claiming_faculty": True},
            {"author_order": 2, "author_name_from_source": "EEE B", "person_type": "FACULTY", "faculty_id": second["id"]},
            {"author_order": 3, "author_name_from_source": "CSE C", "person_type": "FACULTY", "faculty_id": third["id"]},
        ],
    })
    assert response.status_code == 201, response.text
    publication_id = response.json()["id"]
    period = "from_date=2026-07-01&to_date=2026-12-31"
    for department in (eee, cse):
        page = client.get(f"/publications?{period}&department_id={department['id']}&page=1&page_size=10")
        assert page.status_code == 200, page.text
        assert page.json()["total"] == 1
        assert [item["id"] for item in page.json()["items"]] == [publication_id]
        dashboard = client.get(f"/publication-dashboard?{period}&dashboard_only=true&department_id={department['id']}")
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["totals"]["total"] == dashboard.json()["totals"]["journal"] == 1
    assert client.get(f"/publications?{period}&department_id=999999").status_code == 422


def test_patent_and_book_apis_apply_shared_department_scope_to_lists_and_dashboards(setup):
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        mec = Department(code="MEC", name="Mechanical Engineering")
        db.add_all([cse, mec]); db.flush()
        eee_first = _faculty(201, "EEE Inventor A", eee.id)
        eee_second = _faculty(202, "EEE Inventor B", eee.id)
        cse_author = _faculty(203, "CSE Contributor", cse.id)
        db.add_all([eee_first, eee_second, cse_author]); db.flush()

        patent = Patent(title="Shared department patent", patent_office="IPO", current_status="FILED", filing_date=date(2026, 9, 1))
        patent.inventors = [
            PatentInventor(inventor_order=1, inventor_name="EEE A", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=201, is_claiming_faculty=True),
            PatentInventor(inventor_order=2, inventor_name="EEE B", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=202),
            PatentInventor(inventor_order=3, inventor_name="CSE", person_type="FACULTY", institution_scope="SAME_INSTITUTION_OTHER_DEPARTMENT", faculty_id=203),
        ]
        work = BookPublication(work_type="BOOK", title="Shared department book", publisher="VCE Press", publication_date=date(2026, 9, 1))
        work.contributors = [
            BookContributor(contributor_order=1, contributor_name="EEE A", role="AUTHOR", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=201, is_claiming_faculty=True),
            BookContributor(contributor_order=2, contributor_name="EEE B", role="AUTHOR", person_type="FACULTY", institution_scope="CURRENT_DEPARTMENT", faculty_id=202),
            BookContributor(contributor_order=3, contributor_name="CSE", role="AUTHOR", person_type="FACULTY", institution_scope="SAME_INSTITUTION_OTHER_DEPARTMENT", faculty_id=203),
        ]
        db.add_all([patent, work]); db.commit()
        patent_id, work_id = patent.id, work.id
        department_ids = (eee.id, cse.id, mec.id)

    period = "from_date=2026-07-01&to_date=2026-12-31"
    for department_id in department_ids[:2]:
        patents = client.get(f"/patents?department_id={department_id}&page=1&page_size=10")
        assert patents.status_code == 200, patents.text
        assert patents.json()["total"] == 1
        assert [item["id"] for item in patents.json()["items"]] == [patent_id]
        patent_dashboard = client.get(f"/patent-dashboard?{period}&department_id={department_id}")
        assert patent_dashboard.status_code == 200, patent_dashboard.text
        assert patent_dashboard.json()["totals"]["unique"] == 1

        books = client.get(f"/books?department_id={department_id}&page=1&page_size=10")
        assert books.status_code == 200, books.text
        assert books.json()["total"] == 1
        assert [item["id"] for item in books.json()["items"]] == [work_id]
        book_dashboard = client.get(f"/book-dashboard?{period}&department_id={department_id}")
        assert book_dashboard.status_code == 200, book_dashboard.text
        assert book_dashboard.json()["totals"]["total"] == book_dashboard.json()["totals"]["books"] == 1

    assert client.get(f"/patents?department_id={department_ids[2]}").json() == []
    assert client.get(f"/books?department_id={department_ids[2]}").json() == []
    assert client.get("/patents?department_id=999999").status_code == 422
    assert client.get("/books?department_id=999999").status_code == 422


def test_fdp_and_certification_apis_scope_lists_and_kpis_by_department(setup):
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        db.add(cse); db.flush()
        eee_faculty = _faculty(301, "EEE Training Faculty", eee.id)
        cse_faculty = _faculty(302, "CSE Training Faculty", cse.id)
        db.add_all([eee_faculty, cse_faculty]); db.flush()
        activity = FdpActivity(title="Shared training", activity_type="WORKSHOP", organizing_institution="VCE", start_date=date(2026, 9, 1), duration_value=1, duration_unit="DAYS")
        activity.participants = [FdpParticipant(faculty_id=301, role="ATTENDEE"), FdpParticipant(faculty_id=302, role="COORDINATOR")]
        completed = Certification(faculty_id=302, name="Completed CSE course", category="MOOC", provider="Provider", status="COMPLETED", completion_date=date(2026, 9, 1))
        in_progress = Certification(faculty_id=302, name="Current CSE course", category="OTHER", provider="Provider", status="IN_PROGRESS")
        db.add_all([activity, completed, in_progress]); db.commit()
        activity_id, completed_id, in_progress_id = activity.id, completed.id, in_progress.id
        eee_id, cse_id = eee.id, cse.id

    period = "from_date=2026-07-01&to_date=2026-12-31"
    for department_id, participant_id in ((eee_id, 301), (cse_id, 302)):
        activities = client.get(f"/fdp-activities?{period}&department_id={department_id}&page=1&page_size=10")
        assert activities.status_code == 200, activities.text
        assert activities.json()["total"] == 1
        assert [row["id"] for row in activities.json()["items"]] == [activity_id]
        dashboard = client.get(f"/fdp-dashboard?{period}&department_id={department_id}")
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["totals"]["activities"] == dashboard.json()["totals"]["faculty_contributors"] == 1
        assert [row["id"] for row in dashboard.json()["faculty_participants"]] == [participant_id]

    certifications = client.get(f"/certifications?department_id={cse_id}&page=1&page_size=all")
    assert certifications.status_code == 200, certifications.text
    assert {row["id"] for row in certifications.json()["items"]} == {completed_id, in_progress_id}
    dashboard = client.get(f"/certification-dashboard?{period}&department_id={cse_id}")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["totals"] == {"certifications": 1, "completed": 1, "in_progress": 1, "faculty_contributors": 1}
    assert client.get(f"/certifications?department_id={eee_id}").json() == []
    assert client.get("/fdp-activities?department_id=999999").status_code == 422
    assert client.get("/certifications?department_id=999999").status_code == 422


def test_funding_apis_scope_distinct_projects_and_financial_totals_by_department(setup):
    """A Department sees each shared parent project once, never once per PI."""
    client, factory, _ = setup
    with factory() as db:
        eee = db.scalar(select(Department).where(Department.code == "EEE"))
        cse = Department(code="CSE", name="Computer Science and Engineering")
        mec = Department(code="MEC", name="Mechanical Engineering", is_active=False)
        db.add_all([cse, mec]); db.flush()
        eee_first = _faculty(401, "EEE Lead", eee.id)
        eee_second = _faculty(402, "EEE Co-PI", eee.id)
        cse_member = _faculty(403, "CSE Co-PI", cse.id)
        db.add_all([eee_first, eee_second, cse_member]); db.flush()

        shared = FundingProject(
            title="Shared sponsored project", category="SPONSORED_RESEARCH",
            department="Recorded EEE", status="SANCTIONED", sanction_date=date(2026, 9, 1),
            proposed_amount=Decimal("2500000.00"), sanctioned_amount=Decimal("2000000.00"),
        )
        shared.faculty = [
            FundingProjectFaculty(faculty_id=401, role="LEAD_PI", affiliation_type="FACULTY_MASTER"),
            FundingProjectFaculty(faculty_id=402, role="CO_PI", affiliation_type="FACULTY_MASTER"),
            FundingProjectFaculty(faculty_id=403, role="CO_PI", affiliation_type="FACULTY_MASTER"),
        ]
        eee_only = FundingProject(
            title="EEE sponsored project", category="SPONSORED_RESEARCH",
            department="Recorded EEE", status="ONGOING", sanction_date=date(2026, 9, 2),
            proposed_amount=Decimal("3000000.00"), sanctioned_amount=Decimal("2000000.00"),
        )
        eee_only.faculty = [FundingProjectFaculty(faculty_id=401, role="MEMBER_PI", affiliation_type="FACULTY_MASTER")]
        consultancy = FundingProject(
            title="Shared consultancy", category="CONSULTANCY", department="Recorded CSE",
            status="COMPLETED", sanction_date=date(2026, 9, 3),
            contract_amount=Decimal("3000000.00"), amount_received=Decimal("1000000.00"),
        )
        consultancy.faculty = [
            FundingProjectFaculty(faculty_id=401, role="LEAD_PI", affiliation_type="FACULTY_MASTER"),
            FundingProjectFaculty(faculty_id=403, role="CO_PI", affiliation_type="FACULTY_MASTER"),
        ]
        internal = FundingProject(
            title="CSE internal grant", category="INTERNAL_GRANT", department="Recorded CSE",
            status="SANCTIONED", sanction_date=date(2026, 9, 4),
            sanctioned_amount=Decimal("500000.00"), amount_utilized=Decimal("125000.00"),
        )
        internal.faculty = [FundingProjectFaculty(faculty_id=403, role="BENEFICIARY", affiliation_type="FACULTY_MASTER")]
        no_sanction_date = FundingProject(
            title="Unverified historical project", category="SPONSORED_RESEARCH",
            department="Recorded EEE", status="DRAFT", proposal_submission_date=date(2026, 9, 5),
        )
        no_sanction_date.faculty = [FundingProjectFaculty(faculty_id=401, role="MEMBER_PI", affiliation_type="FACULTY_MASTER")]
        db.add_all([shared, eee_only, consultancy, internal, no_sanction_date]); db.commit()
        ids = {"shared": shared.id, "eee_only": eee_only.id, "consultancy": consultancy.id, "internal": internal.id, "no_sanction_date": no_sanction_date.id}
        department_ids = {"eee": eee.id, "cse": cse.id, "mec": mec.id}

    period = "from_date=2026-07-01&to_date=2026-12-31"
    eee_projects = client.get(f"/funding-projects?{period}&category=SPONSORED_RESEARCH&department_id={department_ids['eee']}&page=1&page_size=all")
    assert eee_projects.status_code == 200, eee_projects.text
    assert eee_projects.json()["total"] == 3
    assert {row["id"] for row in eee_projects.json()["items"]} == {ids["shared"], ids["eee_only"], ids["no_sanction_date"]}

    # The submitted/no-sanction proposal remains in the project universe for
    # normal reporting-date filters, but only awarded records contribute to
    # sanctioned money. Two EEE contributors on ``shared`` do not double it.
    eee_dashboard = client.get(f"/funding-dashboard?{period}&category=SPONSORED_RESEARCH&department_id={department_ids['eee']}")
    assert eee_dashboard.status_code == 200, eee_dashboard.text
    assert eee_dashboard.json()["totals"]["sanctioned_amount"] == 4000000
    assert {row["id"] for row in eee_dashboard.json()["faculty"]} == {401, 402}
    assert eee_dashboard.json()["totals"]["faculty_contributors"] == 2

    cse_projects = client.get(f"/funding-projects?{period}&category=SPONSORED_RESEARCH&department_id={department_ids['cse']}&page=1&page_size=all")
    assert cse_projects.status_code == 200, cse_projects.text
    assert [row["id"] for row in cse_projects.json()["items"]] == [ids["shared"]]
    cse_dashboard = client.get(f"/funding-dashboard?{period}&category=SPONSORED_RESEARCH&department_id={department_ids['cse']}")
    assert cse_dashboard.status_code == 200, cse_dashboard.text
    assert cse_dashboard.json()["totals"]["sanctioned_amount"] == 2000000
    assert [row["id"] for row in cse_dashboard.json()["faculty"]] == [403]

    for category, identity in (("CONSULTANCY", ids["consultancy"]), ("INTERNAL_GRANT", ids["internal"])):
        response = client.get(f"/funding-projects?{period}&category={category}&department_id={department_ids['cse']}&page=1&page_size=all")
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()["items"]] == [identity]
    assert client.get(f"/funding-projects?{period}&department_id={department_ids['mec']}&page=1&page_size=all").json()["items"] == []
    assert client.get(f"/funding-projects?{period}&department_id=999999&page=1&page_size=all").status_code == 422

    historical = client.get(f"/funding-projects?{period}&category=SPONSORED_RESEARCH&department_id={department_ids['eee']}&attribution_mode=AT_ACTIVITY_DATE&page=1&page_size=all")
    assert historical.status_code == 200, historical.text
    assert {row["id"] for row in historical.json()["items"]} == {ids["shared"], ids["eee_only"]}
