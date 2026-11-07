from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import select

from backend.models import Publication, PublicationReportTemplate
from conftest import author, paper


def request(fields, **extra):
    return {
        "fields": fields,
        "publication_type": "ALL",
        "period_mode": "CUSTOM",
        "from_date": "2026-07-01",
        "to_date": "2027-06-30",
        "row_mode": "PUBLICATION",
        "sort": "DATE_DESC",
        **extra,
    }


def seed(client):
    first = paper("10.1234/report-one", "2026-09-18")
    first["title"] = "A reportable journal paper"
    first["volume"] = "4"
    first["issue"] = "2"
    first["pages_or_article_number"] = "10-19"
    first["authors"][0]["author_name_from_source"] = "Faculty A"
    first["authors"][1]["author_name_from_source"] = "Faculty B"
    first["authors"][1]["is_corresponding_author"] = True
    assert client.post("/publications", json=first).status_code == 201
    second = paper("10.1234/report-two", "2026-10-01")
    second["title"] = "A reportable conference paper"
    second["publication_type"] = "CONFERENCE"
    second["conference_name"] = "Test Conference"
    second["proceedings_title"] = "Proceedings of Test Conference"
    second["authors"] = [author(1, "FACULTY", 2, True), author(2, "EXTERNAL")]
    assert client.post("/publications", json=second).status_code == 201


def test_report_preview_field_catalogue_and_row_modes(setup):
    client, _, _ = setup
    seed(client)
    catalogue = client.get("/publication-reports/fields")
    assert catalogue.status_code == 200
    fields = {field["id"]: field for field in catalogue.json()["fields"]}
    assert fields["publication_title"]["availability"] == "AVAILABLE"
    assert fields["vardhaman_faculty_authors"]["availability"] == "CALCULATED"
    assert fields["department"]["availability"] == "UNAVAILABLE"
    assert fields["classification"]["availability"] == "AVAILABLE"
    assert fields["sci_indexed"]["availability"] == "CALCULATED"
    assert "conference_type" not in fields
    assert {"starting_page", "ending_page", "conference_acronym", "funding_acknowledgement", "funded_publication", "corresponding_institution"}.isdisjoint(fields)
    assert fields["page_range"]["availability"] == "AVAILABLE"
    assert fields["article_number"]["availability"] == "UNAVAILABLE"

    payload = request(["serial_number", "publication_title", "vardhaman_faculty_authors", "all_authors", "volume_issue", "doi_url"])
    preview = client.post("/publication-reports/preview", json=payload)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["total"] == data["unique_publication_count"] == 2
    first = data["items"][0]["values"]
    assert first["serial_number"] == 1
    assert first["doi_url"].startswith("https://doi.org/10.1234/")
    assert "Faculty" in first["vardhaman_faculty_authors"]

    faculty_rows = client.post("/publication-reports/preview", json=request(["faculty_name", "faculty_employee_id", "faculty_author_position"], row_mode="FACULTY", faculty_ids=[1, 2]))
    assert faculty_rows.status_code == 200, faculty_rows.text
    assert faculty_rows.json()["total"] == 2
    assert faculty_rows.json()["unique_publication_count"] == 2
    assert {row["faculty_id"] for row in faculty_rows.json()["items"]} == {1, 2}
    unavailable = client.post("/publication-reports/preview", json=request(["department"]))
    assert unavailable.status_code == 422


def test_report_claimants_are_distinct_from_faculty_authors_and_match_excel_export(setup):
    client, factory, _ = setup
    seed(client)
    fields = ["publication_id", "publication_title", "faculty_name", "faculty_employee_id", "vardhaman_faculty_authors", "all_authors"]

    publication_rows = client.post("/publication-reports/preview", json=request(fields, page_size="all"))
    assert publication_rows.status_code == 200, publication_rows.text
    publication_data = publication_rows.json()
    assert publication_data["total"] == publication_data["unique_publication_count"] == 2
    values_by_title = {item["values"]["publication_title"]: item["values"] for item in publication_data["items"]}
    journal = values_by_title["A reportable journal paper"]
    assert journal["faculty_name"] == "Faculty A"
    assert journal["vardhaman_faculty_authors"] == "Faculty A; Faculty B"
    assert journal["all_authors"] == "Faculty A; Faculty B; STUDENT 1; EXTERNAL Y"

    faculty_rows = client.post("/publication-reports/preview", json=request(fields, row_mode="FACULTY", page_size="all"))
    assert faculty_rows.status_code == 200, faculty_rows.text
    faculty_data = faculty_rows.json()
    assert faculty_data["total"] == 2
    assert {item["faculty_id"] for item in faculty_data["items"]} == {1, 2}
    claimant_journal = next(item["values"] for item in faculty_data["items"] if item["values"]["publication_title"] == "A reportable journal paper")
    assert claimant_journal["faculty_name"] == "Faculty A"
    assert claimant_journal["vardhaman_faculty_authors"] == "Faculty A; Faculty B"

    # Faculty 2 is a coauthor of the journal paper but only claims the conference paper.
    coauthor_filter = client.post("/publication-reports/preview", json=request(fields, row_mode="FACULTY", faculty_ids=[2], page_size="all"))
    assert coauthor_filter.status_code == 200, coauthor_filter.text
    assert [item["values"]["publication_title"] for item in coauthor_filter.json()["items"]] == ["A reportable conference paper"]

    exported = client.post("/publication-reports/export/xlsx", json=request(fields, page_size="all"))
    assert exported.status_code == 200, exported.text
    worksheet = load_workbook(BytesIO(exported.content), read_only=True).active
    headers = [cell.value for cell in next(worksheet.iter_rows(min_row=3, max_row=3))]
    exported_rows = {
        row[headers.index("Publication Title")]: row[headers.index("Faculty Name")]
        for row in worksheet.iter_rows(min_row=4, values_only=True)
    }
    assert exported_rows["A reportable journal paper"] == journal["faculty_name"]

    # Historical records can legitimately lack a claimant. They must not turn every
    # Faculty-linked coauthor into a claimant in a publication-wise report.
    with factory() as db:
        journal_record = db.scalar(select(Publication).where(Publication.doi == "10.1234/report-one"))
        for publication_author in journal_record.authors:
            publication_author.is_claiming_faculty = False
        db.commit()
    unclaimed = client.post("/publication-reports/preview", json=request(fields, title_keyword="journal", page_size="all"))
    assert unclaimed.status_code == 200, unclaimed.text
    assert unclaimed.json()["items"][0]["values"]["faculty_name"] == ""
    assert unclaimed.json()["items"][0]["values"]["vardhaman_faculty_authors"] == "Faculty A; Faculty B"
    unclaimed_faculty_rows = client.post("/publication-reports/preview", json=request(fields, row_mode="FACULTY", title_keyword="journal", page_size="all"))
    assert unclaimed_faculty_rows.status_code == 200, unclaimed_faculty_rows.text
    assert unclaimed_faculty_rows.json()["total"] == 0
    assert unclaimed_faculty_rows.json()["unique_publication_count"] == 1


def test_report_classification_and_indexing_flags_use_stored_publication_values(setup):
    client, _, _ = setup
    cases = [
        ("INTERNATIONAL", "JOURNAL", []),
        ("NATIONAL", "CONFERENCE", ["SCI"]),
        ("OTHER", "JOURNAL", ["NONE"]),
        ("UNKNOWN", "CONFERENCE", ["UNKNOWN"]),
    ]
    for index, (classification, publication_type, indexing) in enumerate(cases, start=1):
        record = paper(f"10.1234/classification-{index}", "2026-09-18")
        record.update(title=f"Classification {classification.title()}", publication_type=publication_type, classification=classification, indexing=indexing)
        if publication_type == "CONFERENCE":
            record.update(conference_name=f"Conference {classification}", proceedings_title=f"Proceedings {classification}")
        response = client.post("/publications", json=record)
        assert response.status_code == 201, response.text

    fields = ["publication_title", "classification", "indexing_databases", "sci_indexed", "scie_indexed", "esci_indexed"]
    preview = client.post("/publication-reports/preview", json=request(fields, page_size="all"))
    assert preview.status_code == 200, preview.text
    rows = {item["values"]["publication_title"]: item["values"] for item in preview.json()["items"]}
    # New configurations treat the stable key as Conference Scope only.
    assert rows["Classification International"]["classification"] == ""
    assert rows["Classification National"]["classification"] == "National"
    assert rows["Classification Other"]["classification"] == ""
    assert rows["Classification Unknown"]["classification"] == "Unknown"
    assert rows["Classification National"]["sci_indexed"] == "Yes"
    assert rows["Classification Other"]["indexing_databases"] == "None"
    assert rows["Classification Unknown"]["indexing_databases"] == "Unknown"
    assert rows["Classification International"]["indexing_databases"] == ""

    legacy_preview = client.post("/publication-reports/preview", json={**request(["conference_type"], page_size="all"), "legacy_classification": True})
    assert legacy_preview.status_code == 200, legacy_preview.text
    assert legacy_preview.json()["headers"] == [{"id": "classification", "heading": "Legacy Classification"}]
    legacy_rows = {item["values"]["classification"] for item in legacy_preview.json()["items"]}
    assert {"International", "National", "Other", "Unknown"}.issubset(legacy_rows)

    exported = client.post("/publication-reports/export/xlsx", json=request(fields, page_size="all"))
    assert exported.status_code == 200, exported.text
    worksheet = load_workbook(BytesIO(exported.content), read_only=True).active
    headers = [cell.value for cell in next(worksheet.iter_rows(min_row=3, max_row=3))]
    exported_rows = {row[headers.index("Publication Title")]: row[headers.index("Conference Scope")]
                     for row in worksheet.iter_rows(min_row=4, values_only=True)}
    assert exported_rows["Classification National"] == rows["Classification National"]["classification"]


def test_report_subtype_quality_applicability_preserves_stored_metadata(setup):
    client, _, _ = setup
    journal = paper("10.1234/batch3-journal", "2026-09-18")
    journal.update(title="Journal quality", publication_type="JOURNAL", quartile="Q1", impact_factor=4.2, classification="INTERNATIONAL")
    conference = paper("10.1234/batch3-conference", "2026-09-19")
    conference.update(title="Conference scope", publication_type="CONFERENCE", quartile="Q2", impact_factor=3.1, classification="NATIONAL", conference_name="Batch 3 Conference")
    assert client.post("/publications", json=journal).status_code == 201
    assert client.post("/publications", json=conference).status_code == 201

    fields = ["publication_title", "quartile", "impact_factor", "classification"]
    preview = client.post("/publication-reports/preview", json=request(fields, page_size="all"))
    assert preview.status_code == 200, preview.text
    rows = {item["values"]["publication_title"]: item["values"] for item in preview.json()["items"]}
    assert rows["Journal quality"] == {"publication_title": "Journal quality", "quartile": "Q1", "impact_factor": 4.2, "classification": ""}
    assert rows["Conference scope"] == {"publication_title": "Conference scope", "quartile": "", "impact_factor": "", "classification": "National"}
    rejected = client.post("/publication-reports/preview", json=request(["publication_title"], publication_type="CONFERENCE", quartile="Q2"))
    assert rejected.status_code == 422


def test_report_indexing_filters_use_exact_json_codes_across_preview_export_and_citations(setup):
    client, _, _ = setup
    cases = [
        ("SCI only", ["SCI"], "Q1", "JOURNAL", 1),
        ("SCIE only", ["SCIE"], "Q2", "JOURNAL", 1),
        ("ESCI only", ["ESCI"], "Q3", "JOURNAL", 1),
        ("Scopus only", ["SCOPUS"], "Q4", "JOURNAL", 1),
        ("SCI and Scopus", ["SCI", "SCOPUS"], "Q2", "CONFERENCE", 1),
        ("Web of Science", ["WEB_OF_SCIENCE"], "Q3", "CONFERENCE", 2),
        ("UGC CARE", ["UGC_CARE"], "Q4", "JOURNAL", 1),
        ("No indexing", ["NONE"], "Q1", "JOURNAL", 1),
        ("Unknown indexing", ["UNKNOWN"], "Q2", "JOURNAL", 1),
        ("Missing indexing", [], "Q3", "JOURNAL", 1),
    ]
    for index, (title, indexing, quartile, publication_type, claimant_id) in enumerate(cases, start=1):
        record = paper(f"10.1234/indexing-{index}", "2026-09-18")
        record.update(title=title, indexing=indexing, quartile=quartile, publication_type=publication_type)
        if claimant_id == 2:
            record["authors"] = [author(1, "FACULTY", 2, True), author(2, "EXTERNAL")]
        if publication_type == "CONFERENCE":
            record.update(conference_name=title, proceedings_title=title)
        response = client.post("/publications", json=record)
        assert response.status_code == 201, response.text

    def titles_for(indexing, **extra):
        response = client.post("/publication-reports/preview", json=request(["publication_title"], indexing=indexing, page_size="all", **extra))
        assert response.status_code == 200, response.text
        return {item["values"]["publication_title"] for item in response.json()["items"]}

    assert titles_for("SCI") == {"SCI only", "SCI and Scopus"}
    assert titles_for("SCIE") == {"SCIE only"}
    assert titles_for("ESCI") == {"ESCI only"}
    assert titles_for("SCOPUS") == {"Scopus only", "SCI and Scopus"}
    assert titles_for("WEB_OF_SCIENCE") == {"Web of Science"}
    assert titles_for("UGC_CARE") == {"UGC CARE"}
    assert titles_for("NONE") == {"No indexing"}
    assert titles_for("UNKNOWN") == {"Unknown indexing"}
    assert "Missing indexing" not in titles_for("UNKNOWN")
    assert titles_for("SCI", quartile="Q1") == {"SCI only"}
    assert titles_for("SCI", publication_type="CONFERENCE") == {"SCI and Scopus"}
    assert titles_for("WEB_OF_SCIENCE", faculty_ids=[2]) == {"Web of Science"}
    assert titles_for("WEB_OF_SCIENCE", faculty_ids=[1]) == set()
    assert titles_for("WEB_OF_SCIENCE", faculty_ids=[1, 2]) == {"Web of Science"}

    preview = client.post("/publication-reports/preview", json=request(["publication_title", "indexing_databases"], indexing="SCI", page_size="all"))
    assert preview.status_code == 200, preview.text
    exported = client.post("/publication-reports/export/xlsx", json=request(["publication_title", "indexing_databases"], indexing="SCI", page_size="all"))
    assert exported.status_code == 200, exported.text
    worksheet = load_workbook(BytesIO(exported.content), read_only=True).active
    headers = [cell.value for cell in next(worksheet.iter_rows(min_row=3, max_row=3))]
    exported_titles = {row[headers.index("Publication Title")] for row in worksheet.iter_rows(min_row=4, values_only=True)}
    assert exported_titles == {item["values"]["publication_title"] for item in preview.json()["items"]}

    citations = client.post("/publication-reports/citations", json={**request(["publication_title"], indexing="SCI"), "citation_style": "IEEE"})
    assert citations.status_code == 200, citations.text
    assert citations.json()["total_selected"] == 2


def test_report_templates_and_citation_completeness(setup):
    client, factory, _ = setup
    seed(client)
    config = {"fields": ["publication_title", "doi"], "headings": {"doi": "DOI Link"}, "row_mode": "PUBLICATION", "sort": "TITLE"}
    created = client.post("/publication-reports/templates", json={"name": "Office register", "description": "Shared office layout", "config": config})
    assert created.status_code == 201, created.text
    identity = created.json()["id"]
    assert client.get("/publication-reports/templates").json()[0]["config"]["headings"]["doi"] == "DOI Link"
    updated = client.put(f"/publication-reports/templates/{identity}", json={"name": "Office register revised", "config": config})
    assert updated.status_code == 200
    assert client.delete(f"/publication-reports/templates/{identity}").status_code == 200
    assert client.post("/publication-reports/templates", json={"name": "Unsafe", "config": {"fields": ["department"]}}).status_code == 422

    # Existing saved layouts are read safely even if they predate a retired field.
    with factory() as db:
        db.add(PublicationReportTemplate(
            name="Legacy page layout",
            config={"fields": ["publication_title", "starting_page", "conference_type"], "headings": {"publication_title": "Title", "starting_page": "Start", "conference_type": "Conference classification"}},
        ))
        db.commit()
    legacy = next(template for template in client.get("/publication-reports/templates").json() if template["name"] == "Legacy page layout")
    assert legacy["config"]["fields"] == ["publication_title", "classification"]
    assert legacy["config"]["headings"] == {"publication_title": "Title", "classification": "Conference classification"}

    citations = client.post("/publication-reports/citations", json={**request(["publication_title"]), "citation_style": "IEEE"})
    assert citations.status_code == 200, citations.text
    data = citations.json()
    assert data["total_selected"] == 2 and data["complete"] == 2
    assert len({item["publication_id"] for item in data["items"]}) == 2
    assert all("reportable" in item["formatted_citation"] for item in data["items"])
