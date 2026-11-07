"""Read-only publication reporting shared by browser previews and exports.

The field catalogue deliberately distinguishes stored/calculated values from fields
that the current publication model cannot verify.  This keeps office reports useful
without turning missing metadata into invented facts.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AcademicYear, Department, Faculty, Publication, PublicationAuthor, PublicationReportTemplate, Student
from .department_filtering import department_record_predicate
from .publication_reporting import P, A, publication_query
from .reporting import validate_date_range
from .services import columns

router = APIRouter(prefix="/publication-reports", tags=["publication-reports"])
DB = Session

AVAILABLE = "AVAILABLE"
CALCULATED = "CALCULATED"
UNAVAILABLE = "UNAVAILABLE"


def field(id: str, label: str, group: str, availability: str, note: str | None = None):
    return {"id": id, "label": label, "group": group, "availability": availability, "note": note}


# Stable field IDs are intentionally independent of user-customised headings.
FIELD_CATALOGUE = [
    # Group 1
    field("faculty_name", "Faculty Name", "Faculty and Author Information", CALCULATED, "Actual publication claimant(s); one claimant per Faculty-wise row."),
    field("faculty_employee_id", "Faculty Employee ID", "Faculty and Author Information", CALCULATED, "Actual publication claimant(s); one claimant per Faculty-wise row."),
    field("department", "Department", "Faculty and Author Information", UNAVAILABLE, "Department is not stored on Faculty Master."),
    field("vardhaman_faculty_authors", "All Vardhaman Faculty Authors", "Faculty and Author Information", CALCULATED),
    field("vardhaman_faculty_count", "Number of Vardhaman Faculty Authors", "Faculty and Author Information", CALCULATED),
    field("all_authors", "All Authors", "Faculty and Author Information", CALCULATED),
    field("first_author", "First Author", "Faculty and Author Information", CALCULATED),
    field("corresponding_author", "Corresponding Author", "Faculty and Author Information", CALCULATED, "Only explicitly marked authors are shown."),
    field("faculty_author_position", "Faculty Author Position", "Faculty and Author Information", CALCULATED, "Requires Faculty-wise rows."),
    field("total_author_count", "Total Number of Authors", "Faculty and Author Information", CALCULATED),
    field("external_authors", "External Authors", "Faculty and Author Information", CALCULATED, "Only explicitly classified external authors are included."),
    field("faculty_contribution_role", "Faculty Contribution Role", "Faculty and Author Information", CALCULATED, "Requires Faculty-wise rows."),
    # Group 2
    field("publication_title", "Publication Title", "Publication Identification", AVAILABLE),
    field("publication_type", "Publication Type", "Publication Identification", AVAILABLE),
    field("publication_year", "Publication Year", "Publication Identification", CALCULATED),
    field("publication_month", "Publication Month", "Publication Identification", CALCULATED),
    field("publication_date", "Publication Date", "Publication Identification", AVAILABLE),
    field("month_year", "Month and Year", "Publication Identification", CALCULATED),
    field("academic_year", "Academic Year", "Publication Identification", CALCULATED, "Matches configured Academic Year Master ranges."),
    field("doi", "DOI", "Publication Identification", AVAILABLE),
    field("doi_url", "DOI URL", "Publication Identification", CALCULATED),
    field("publication_id", "Internal Publication ID", "Publication Identification", AVAILABLE),
    # Group 3
    field("journal_name", "Journal Name", "Journal Publication Details", CALCULATED, "Journal rows only."),
    field("publisher", "Publisher", "Journal Publication Details", AVAILABLE),
    field("volume", "Volume", "Journal Publication Details", AVAILABLE),
    field("issue", "Issue", "Journal Publication Details", AVAILABLE),
    field("volume_issue", "Volume and Issue", "Journal Publication Details", CALCULATED),
    field("page_range", "Page Range", "Journal Publication Details", AVAILABLE),
    field("article_number", "Article Number", "Journal Publication Details", UNAVAILABLE, "Cannot reliably distinguish it from stored pages."),
    field("issn", "ISSN", "Journal Publication Details", AVAILABLE),
    field("eissn", "eISSN", "Journal Publication Details", AVAILABLE),
    # Group 4
    field("conference_paper_title", "Conference Paper Title", "Conference Publication Details", CALCULATED, "Uses publication title for conference rows."),
    field("conference_name", "Conference Name", "Conference Publication Details", AVAILABLE),
    field("proceedings_title", "Proceedings Title", "Conference Publication Details", AVAILABLE),
    field("conference_organizer", "Conference Organizer", "Conference Publication Details", AVAILABLE),
    field("conference_location", "Conference Location", "Conference Publication Details", AVAILABLE),
    field("conference_start_date", "Conference Start Date", "Conference Publication Details", AVAILABLE),
    field("conference_end_date", "Conference End Date", "Conference Publication Details", AVAILABLE),
    field("conference_year", "Conference Year", "Conference Publication Details", CALCULATED),
    field("conference_publisher", "Publisher", "Conference Publication Details", AVAILABLE),
    field("isbn", "ISBN", "Conference Publication Details", AVAILABLE),
    field("conference_volume", "Volume", "Conference Publication Details", AVAILABLE),
    field("conference_page_range", "Page Range", "Conference Publication Details", AVAILABLE),
    field("conference_doi", "DOI", "Conference Publication Details", AVAILABLE),
    # Group 5
    field("indexing_databases", "Indexing Databases", "Indexing and Research Quality", AVAILABLE),
    field("scopus_indexed", "Scopus Indexed", "Indexing and Research Quality", CALCULATED),
    field("sci_indexed", "SCI Indexed", "Indexing and Research Quality", CALCULATED),
    field("scie_indexed", "SCIE Indexed", "Indexing and Research Quality", CALCULATED),
    field("esci_indexed", "ESCI Indexed", "Indexing and Research Quality", CALCULATED),
    field("web_of_science_indexed", "Web of Science Indexed", "Indexing and Research Quality", CALCULATED),
    field("ugc_care_listed", "UGC CARE Listed", "Indexing and Research Quality", CALCULATED),
    field("quartile", "Quartile", "Indexing and Research Quality", AVAILABLE),
    field("impact_factor", "Impact Factor", "Indexing and Research Quality", AVAILABLE),
    field("classification", "Conference Scope", "Conference Metadata", AVAILABLE, "Conference rows only. Historical templates may request the raw legacy classification value."),
    # Group 6
    field("internal_author_count", "Number of Internal Authors", "Institutional and Collaboration Details", CALCULATED),
    field("external_author_count", "Number of External Authors", "Institutional and Collaboration Details", CALCULATED),
    field("collaborative_institutions", "Collaborative Institutions", "Institutional and Collaboration Details", UNAVAILABLE, "No verified institution relationship is stored."),
    field("international_collaboration", "International Collaboration", "Institutional and Collaboration Details", UNAVAILABLE, "Countries are not verified in the model."),
    field("country_of_collaboration", "Country of Collaboration", "Institutional and Collaboration Details", UNAVAILABLE, "Countries are not stored."),
    field("student_coauthors", "Student Coauthors", "Institutional and Collaboration Details", CALCULATED),
    field("student_author_count", "Number of Student Authors", "Institutional and Collaboration Details", CALCULATED),
    # Group 7
    field("record_created_date", "Record Created Date", "Administrative and Evidence Information", AVAILABLE),
    field("evidence_available", "Evidence Available", "Administrative and Evidence Information", CALCULATED),
    field("evidence_type", "Evidence Type", "Administrative and Evidence Information", CALCULATED),
    field("evidence_file_name", "Evidence File Name", "Administrative and Evidence Information", CALCULATED),
    # Group 8
    field("serial_number", "Serial Number", "Calculated and Report-Specific Fields", CALCULATED),
    field("citation_ieee", "Citation (IEEE)", "Calculated and Report-Specific Fields", CALCULATED),
    field("citation_apa", "Citation (APA 7th)", "Calculated and Report-Specific Fields", CALCULATED),
    field("citation_harvard", "Citation (Harvard)", "Calculated and Report-Specific Fields", CALCULATED),
    field("institutional_faculty_count", "Institutional Faculty Count", "Calculated and Report-Specific Fields", CALCULATED),
    field("missing_metadata_fields", "Missing Metadata Fields", "Calculated and Report-Specific Fields", CALCULATED),
    field("citation_completeness", "Citation Completeness", "Calculated and Report-Specific Fields", CALCULATED),
]
FIELDS = {item["id"]: item for item in FIELD_CATALOGUE}
SELECTABLE = {item["id"] for item in FIELD_CATALOGUE if item["availability"] != UNAVAILABLE}
RETIRED_FIELD_IDS = {
    "starting_page", "ending_page", "conference_acronym",
    "funding_acknowledgement", "funded_publication", "corresponding_institution",
    "conference_type",
}
LEGACY_FIELD_ALIASES = {"conference_type": "classification"}
DEFAULT_FIELDS = ["serial_number", "publication_title", "vardhaman_faculty_authors", "all_authors", "journal_name", "publication_date", "doi"]
TEMPLATES = {
    "GENERAL_REGISTER": ["serial_number", "vardhaman_faculty_authors", "publication_title", "publication_type", "journal_name", "volume_issue", "page_range", "publication_date", "doi"],
    "RESEARCH_QUALITY": ["serial_number", "publication_title", "vardhaman_faculty_authors", "indexing_databases", "quartile", "impact_factor", "doi"],
    "DEPARTMENT_CONSOLIDATED": ["serial_number", "publication_title", "all_authors", "vardhaman_faculty_authors", "journal_name", "publication_year", "doi"],
}
SORTS = {"DATE_DESC", "DATE_ASC", "YEAR", "FACULTY", "TITLE", "VENUE"}


class ReportRequest(BaseModel):
    faculty_ids: list[int] = Field(default_factory=list)
    publication_type: Literal["ALL", "JOURNAL", "CONFERENCE"] = "ALL"
    period_mode: Literal["ALL", "ACADEMIC_YEAR", "CUSTOM"] = "ALL"
    academic_year_id: int | None = None
    from_date: date | None = None
    to_date: date | None = None
    title_keyword: str | None = Field(default=None, max_length=250)
    venue_keyword: str | None = Field(default=None, max_length=250)
    publication_year: int | None = Field(default=None, ge=1900, le=2500)
    indexing: str | None = None
    quartile: str | None = None
    legacy_classification: bool = False
    # LEGACY preserves requests/templates created before Phase 3A.
    scope_type: Literal["LEGACY", "INSTITUTION", "DEPARTMENT", "FACULTY"] = "LEGACY"
    department_id: int | None = None
    attribution_mode: Literal["CURRENT", "AT_ACTIVITY_DATE"] = "CURRENT"
    scope_faculty_id: int | None = None
    faculty_relationship: Literal["CLAIMING", "CONTRIBUTING"] = "CLAIMING"
    row_mode: Literal["PUBLICATION", "FACULTY"] = "PUBLICATION"
    sort: Literal["DATE_DESC", "DATE_ASC", "YEAR", "FACULTY", "TITLE", "VENUE"] = "DATE_DESC"
    fields: list[str] = Field(default_factory=lambda: list(DEFAULT_FIELDS))
    headings: dict[str, str] = Field(default_factory=dict)
    page: int = Field(default=1, ge=1)
    page_size: int | Literal["all"] = 25

    @field_validator("faculty_ids")
    @classmethod
    def unique_faculty_ids(cls, value):
        return list(dict.fromkeys(value))

    @field_validator("fields")
    @classmethod
    def normalize_legacy_field_ids(cls, value):
        return list(dict.fromkeys(LEGACY_FIELD_ALIASES.get(field_id, field_id) for field_id in value))

    @model_validator(mode="after")
    def valid_request(self):
        if self.period_mode == "ACADEMIC_YEAR" and not self.academic_year_id:
            raise ValueError("Select an Academic Year")
        if self.period_mode == "CUSTOM":
            validate_date_range(self.from_date, self.to_date)
        if self.quartile and self.publication_type == "CONFERENCE":
            raise ValueError("Quartile is available only for Journal publications")
        if self.scope_type == "DEPARTMENT" and self.department_id is None:
            raise ValueError("Department scope requires department_id")
        if self.scope_type == "FACULTY" and self.scope_faculty_id is None:
            raise ValueError("Faculty scope requires scope_faculty_id")
        if self.scope_type in {"INSTITUTION", "LEGACY"} and (self.department_id is not None or self.scope_faculty_id is not None):
            raise ValueError("Department or Faculty IDs require the matching reporting scope")
        if self.page_size != "all" and self.page_size not in (10, 25, 50):
            raise ValueError("Page size must be 10, 25, 50 or all")
        invalid = set(self.fields) - SELECTABLE
        if invalid:
            raise ValueError(f"Unavailable or unknown report fields: {', '.join(sorted(invalid))}")
        if not self.fields:
            raise ValueError("Select at least one report column")
        legacy_heading = self.headings.pop("conference_type", None)
        if legacy_heading and "classification" in self.fields and "classification" not in self.headings:
            self.headings["classification"] = legacy_heading
        if set(self.headings) - set(self.fields):
            raise ValueError("Custom headings must belong to selected fields")
        return self


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    config: dict

    @field_validator("config")
    @classmethod
    def safe_config(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Template configuration must be an object")
        raw_fields = value.get("fields", DEFAULT_FIELDS)
        if not isinstance(raw_fields, list):
            raise ValueError("Template fields must be a list")
        fields = list(dict.fromkeys(LEGACY_FIELD_ALIASES.get(field_id, field_id) for field_id in raw_fields))
        if set(fields) - SELECTABLE:
            raise ValueError("Template contains unavailable or unknown field IDs")
        headings = value.get("headings", {})
        if isinstance(headings, dict):
            headings = {LEGACY_FIELD_ALIASES.get(field_id, field_id): heading for field_id, heading in headings.items() if LEGACY_FIELD_ALIASES.get(field_id, field_id) in fields}
        return {**value, "fields": fields, "headings": headings}


def _supported_template_config(config: dict | None):
    """Return a read-safe template configuration without retired report fields."""
    source = config if isinstance(config, dict) else {}
    configured_fields = source.get("fields", DEFAULT_FIELDS)
    if not isinstance(configured_fields, list):
        configured_fields = list(DEFAULT_FIELDS)
    normalized_fields = [LEGACY_FIELD_ALIASES.get(field_id, field_id) for field_id in configured_fields]
    fields = list(dict.fromkeys(field_id for field_id in normalized_fields if field_id in SELECTABLE and field_id not in RETIRED_FIELD_IDS))
    headings = source.get("headings", {})
    return {
        **source,
        "fields": fields or list(DEFAULT_FIELDS),
        # Old templates predate subtype-aware terminology. Preserve their
        # stored classification request as an explicit read-only compatibility
        # mode; opening a template never writes this marker back to the DB.
        "legacy_classification": bool("classification" in fields and (source.get("legacy_classification") or source.get("field_semantics_version") != 3)),
        "headings": {LEGACY_FIELD_ALIASES.get(field_id, field_id): heading for field_id, heading in headings.items()
                     if LEGACY_FIELD_ALIASES.get(field_id, field_id) in fields}
        if isinstance(headings, dict) else {},
    }


def _label(value: str | None):
    return (value or "").replace("_", " ").title()


def _as_date(value: date | None):
    return value.isoformat() if value else ""


def _year_name(pub: Publication, years: list[AcademicYear]):
    for year in years:
        if year.start_date <= pub.publication_date <= year.end_date:
            return year.name
    return ""


def _index_flag(pub: Publication, value: str):
    if value in (pub.indexing or []):
        return "Yes"
    if "NONE" in (pub.indexing or []):
        return "No"
    return "Unknown"


def _indexing_membership(value: str):
    """Exact JSON-array membership for report filters.

    Unlike dashboard KPI semantics, a report filter for UNKNOWN means an
    explicitly recorded UNKNOWN value; an empty indexing list remains missing
    metadata rather than an implicit category.
    """
    values = func.json_each(P.indexing).table_valued("value").alias()
    return exists(select(1).select_from(values).where(values.c.value == value))


def _citation_data(pub: Publication, author_names: list[str]):
    missing = []
    if not author_names:
        missing.append("authors")
    if not pub.title:
        missing.append("title")
    if not pub.publication_date:
        missing.append("publication year")
    venue = pub.journal_conference_name or pub.conference_name or pub.proceedings_title
    if not venue:
        missing.append("journal or conference venue")
    status = "NEEDS_REVIEW" if "title" in missing else "INCOMPLETE" if missing else "COMPLETE"
    return {"authors": author_names, "venue": venue or "", "missing": missing, "status": status}


def _citation(pub: Publication, author_names: list[str], style: str):
    data = _citation_data(pub, author_names)
    authors = ", ".join(author_names) if author_names else "[Author unavailable]"
    year = str(pub.publication_date.year) if pub.publication_date else ("n.d." if style in {"APA", "HARVARD"} else "")
    title = pub.title or "[Title unavailable]"
    venue = data["venue"]
    volume_issue = " ".join(filter(None, [pub.volume, f"({pub.issue})" if pub.issue else ""]))
    location = ", ".join(filter(None, [pub.conference_location, pub.publisher])) if pub.publication_type == "CONFERENCE" else pub.publisher or ""
    pages = pub.pages_or_article_number or ""
    doi = f"https://doi.org/{pub.doi}" if pub.doi else ""
    pieces = {
        "IEEE": [authors, f'“{title}.”', venue, volume_issue, pages, year, doi],
        "APA": [authors, f"({year}).", title + ".", venue, volume_issue, pages, doi],
        "HARVARD": [authors, f"({year})", title + ".", venue, volume_issue, pages, location, doi],
    }[style]
    return ", ".join(part.strip(" ,") for part in pieces if part).replace(". ,", ".")


def _selection(db: Session, request: ReportRequest):
    query = publication_query(include_inactive=False, dashboard_only=True)
    if request.period_mode == "ACADEMIC_YEAR":
        year = db.get(AcademicYear, request.academic_year_id)
        if not year:
            raise HTTPException(422, "Unknown Academic Year")
        query = query.where(P.publication_date.between(year.start_date, year.end_date))
    elif request.period_mode == "CUSTOM":
        query = query.where(P.publication_date.between(request.from_date, request.to_date))
    if request.publication_type != "ALL":
        query = query.where(P.publication_type == request.publication_type)
    if request.scope_type == "DEPARTMENT":
        if db.get(Department, request.department_id) is None:
            raise HTTPException(422, "Unknown Department ID")
        query = query.where(department_record_predicate(db, "publications", request.department_id, attribution_mode=request.attribution_mode))
    elif request.scope_type == "FACULTY":
        if db.get(Faculty, request.scope_faculty_id) is None:
            raise HTTPException(422, "Unknown Faculty ID")
        if request.faculty_relationship == "CLAIMING":
            query = query.where(P.authors.any((A.faculty_id == request.scope_faculty_id) & A.is_claiming_faculty.is_(True)))
        else:
            query = query.where(P.authors.any(A.faculty_id == request.scope_faculty_id))
    if request.faculty_ids:
        if request.row_mode == "FACULTY":
            # A Faculty-wise report is claimant-specific: one author association
            # must satisfy both the selected Faculty and claimant conditions.
            query = query.where(P.authors.any(
                (A.faculty_id.in_(request.faculty_ids)) & A.is_claiming_faculty.is_(True)
            ))
        else:
            # Publication-wise filtering retains the established general meaning:
            # a selected Faculty may be an identified coauthor without claiming.
            query = query.where(P.authors.any(A.faculty_id.in_(request.faculty_ids)))
    if request.title_keyword:
        query = query.where(P.title.ilike(f"%{request.title_keyword}%"))
    if request.venue_keyword:
        query = query.where((P.journal_conference_name.ilike(f"%{request.venue_keyword}%")) | (P.conference_name.ilike(f"%{request.venue_keyword}%")) | (P.proceedings_title.ilike(f"%{request.venue_keyword}%")))
    if request.publication_year:
        query = query.where(P.publication_date.between(date(request.publication_year, 1, 1), date(request.publication_year, 12, 31)))
    if request.indexing:
        query = query.where(_indexing_membership(request.indexing))
    if request.quartile:
        query = query.where(P.quartile == request.quartile)
    return db.scalars(query.order_by(P.publication_date.desc(), P.id.desc())).unique().all()


def _build_rows(db: Session, request: ReportRequest):
    publications = _selection(db, request)
    faculty = {person.id: person for person in db.scalars(select(Faculty)).all()}
    students = {person.id: person for person in db.scalars(select(Student)).all()}
    years = db.scalars(select(AcademicYear).order_by(AcademicYear.start_date.desc())).all()
    rows = []
    for pub in publications:
        author_names = [author.author_name_from_source for author in sorted(pub.authors, key=lambda item: item.author_order)]
        faculty_authors = [author for author in sorted(pub.authors, key=lambda item: item.author_order)
                           if author.faculty_id and author.faculty_id in faculty]
        claimant_authors = [author for author in faculty_authors if author.is_claiming_faculty]
        student_authors = [author for author in pub.authors if author.student_id and author.student_id in students]
        contexts = [None]
        if request.row_mode == "FACULTY":
            contexts = [author for author in claimant_authors
                        if not request.faculty_ids or author.faculty_id in request.faculty_ids]
        for context in contexts:
            row = _values(pub, context, faculty, students, years, author_names, faculty_authors, claimant_authors, student_authors, request)
            row["_publication"] = pub
            row["_author_names"] = author_names
            rows.append(row)
    sort_key = {
        "DATE_DESC": lambda row: (row["_publication"].publication_date, row["_publication"].id),
        "DATE_ASC": lambda row: (row["_publication"].publication_date, row["_publication"].id),
        "YEAR": lambda row: (row["_publication"].publication_date.year, row["_publication"].title.casefold(), row["_publication"].id),
        "FACULTY": lambda row: (str(row.get("faculty_name", "")).casefold(), row["_publication"].title.casefold(), row["_publication"].id),
        "TITLE": lambda row: (row["_publication"].title.casefold(), row["_publication"].id),
        "VENUE": lambda row: ((row["_publication"].journal_conference_name or "").casefold(), row["_publication"].title.casefold(), row["_publication"].id),
    }[request.sort]
    rows.sort(key=sort_key, reverse=request.sort == "DATE_DESC")
    for index, row in enumerate(rows, start=1):
        row["serial_number"] = index
    return rows, len(publications)


def _values(pub, context, faculty, students, years, author_names, faculty_authors, claimant_authors, student_authors, request):
    current = faculty.get(context.faculty_id) if context else None
    faculty_names = [faculty[author.faculty_id].name for author in faculty_authors]
    claimant_names = [faculty[author.faculty_id].name for author in claimant_authors]
    claimant_employee_ids = [faculty[author.faculty_id].employee_id or "" for author in claimant_authors]
    student_names = [students[author.student_id].name for author in student_authors]
    external_names = [author.author_name_from_source for author in pub.authors if author.person_type == "EXTERNAL"]
    corresponding = [author.author_name_from_source for author in pub.authors if author.is_corresponding_author]
    citation = _citation_data(pub, author_names)
    role = ""
    if context:
        role = "; ".join(filter(None, ["First author" if context.is_first_author else "", "Corresponding author" if context.is_corresponding_author else "", "Coauthor" if not context.is_first_author and not context.is_corresponding_author else ""]))
    value = {
        "_faculty_id": current.id if current else None,
        "faculty_name": current.name if current else "; ".join(claimant_names),
        "faculty_employee_id": current.employee_id if current else "; ".join(filter(None, claimant_employee_ids)),
        "department": "",
        "vardhaman_faculty_authors": "; ".join(faculty_names),
        "vardhaman_faculty_count": len(faculty_names),
        "all_authors": "; ".join(author_names),
        "first_author": author_names[0] if author_names else "",
        "corresponding_author": "; ".join(corresponding),
        "faculty_author_position": context.author_order if context else "",
        "total_author_count": len(author_names),
        "external_authors": "; ".join(external_names),
        "faculty_contribution_role": role,
        "publication_title": pub.title,
        "publication_type": _label(pub.publication_type),
        "publication_year": pub.publication_date.year,
        "publication_month": pub.publication_date.strftime("%B"),
        "publication_date": _as_date(pub.publication_date),
        "month_year": pub.publication_date.strftime("%B %Y"),
        "academic_year": _year_name(pub, years),
        "doi": pub.doi or "",
        "doi_url": f"https://doi.org/{pub.doi}" if pub.doi else "",
        "publication_id": pub.id,
        "journal_name": pub.journal_conference_name if pub.publication_type == "JOURNAL" else "",
        "publisher": pub.publisher or "",
        "volume": pub.volume or "",
        "issue": pub.issue or "",
        "volume_issue": " ".join(filter(None, [pub.volume or "", f"({pub.issue})" if pub.issue else ""])),
        "page_range": pub.pages_or_article_number or "",
        "issn": pub.issn or "",
        "eissn": pub.eissn or "",
        "conference_paper_title": pub.title if pub.publication_type == "CONFERENCE" else "",
        "conference_name": pub.conference_name or (pub.journal_conference_name if pub.publication_type == "CONFERENCE" else ""),
        "proceedings_title": pub.proceedings_title or "",
        "conference_organizer": pub.conference_organizer or "",
        "conference_location": pub.conference_location or "",
        "conference_start_date": _as_date(pub.conference_start_date),
        "conference_end_date": _as_date(pub.conference_end_date),
        "conference_year": pub.conference_start_date.year if pub.conference_start_date else "",
        "conference_publisher": pub.publisher or "",
        "isbn": pub.isbn or "",
        "conference_volume": pub.volume or "",
        "conference_page_range": pub.pages_or_article_number or "",
        "conference_doi": pub.doi or "",
        "indexing_databases": "; ".join(_label(item) for item in pub.indexing or []),
        "scopus_indexed": _index_flag(pub, "SCOPUS"),
        "sci_indexed": _index_flag(pub, "SCI"),
        "scie_indexed": _index_flag(pub, "SCIE"),
        "esci_indexed": _index_flag(pub, "ESCI"),
        "web_of_science_indexed": _index_flag(pub, "WEB_OF_SCIENCE"),
        "ugc_care_listed": _index_flag(pub, "UGC_CARE"),
        "quartile": (pub.quartile or "") if pub.publication_type == "JOURNAL" else "",
        "impact_factor": pub.impact_factor if pub.publication_type == "JOURNAL" and pub.impact_factor is not None else "",
        "classification": _label(pub.classification) if pub.publication_type == "CONFERENCE" or request.legacy_classification else "",
        "internal_author_count": len(faculty_authors) + len(student_authors),
        "external_author_count": len(external_names),
        "student_coauthors": "; ".join(student_names),
        "student_author_count": len(student_names),
        "record_created_date": _as_date(pub.created_at.date() if pub.created_at else None),
        "evidence_available": "Yes" if pub.evidence else "No",
        "evidence_type": "; ".join(sorted({e.evidence_type for e in pub.evidence})),
        "evidence_file_name": "; ".join(e.original_filename for e in pub.evidence),
        "institutional_faculty_count": len(faculty_names),
        "missing_metadata_fields": "; ".join(citation["missing"]),
        "citation_completeness": citation["status"],
        "citation_ieee": _citation(pub, author_names, "IEEE"),
        "citation_apa": _citation(pub, author_names, "APA"),
        "citation_harvard": _citation(pub, author_names, "HARVARD"),
    }
    return value


def _response_rows(rows, request):
    headers = [{"id": field_id, "heading": _heading(request, field_id)} for field_id in request.fields]
    return [{"publication_id": row["_publication"].id, "faculty_id": row.get("_faculty_id"),
             "values": {field_id: row.get(field_id, "") for field_id in request.fields}} for row in rows], headers


def _heading(request: ReportRequest, field_id: str):
    return request.headings.get(field_id) or ("Legacy Classification" if field_id == "classification" and request.legacy_classification else FIELDS[field_id]["label"])


def _scope_metadata(db: Session, request: ReportRequest):
    if request.scope_type in {"LEGACY", "INSTITUTION"}:
        return {"type": request.scope_type, "label": "Institution — Vardhaman College of Engineering"}
    if request.scope_type == "DEPARTMENT":
        department = db.get(Department, request.department_id)
        return {"type": "DEPARTMENT", "department_id": request.department_id,
                "attribution_mode": request.attribution_mode,
                "label": f"Department — {department.name} ({department.code}) · {'Activity-Date' if request.attribution_mode == 'AT_ACTIVITY_DATE' else 'Current'} Department Attribution"}
    faculty = db.get(Faculty, request.scope_faculty_id)
    return {"type": "FACULTY", "faculty_id": request.scope_faculty_id,
            "relationship": request.faculty_relationship,
            "label": f"Faculty — {faculty.name}{f' ({faculty.employee_id})' if faculty.employee_id else ''} · {request.faculty_relationship.title()} Faculty"}


@router.get("/fields")
def fields():
    return {"fields": FIELD_CATALOGUE, "built_in_templates": [{"id": key, "name": _label(key), "fields": value} for key, value in TEMPLATES.items()]}


@router.post("/preview")
def preview(request: ReportRequest, db: Session = Depends(get_db)):
    rows, unique_count = _build_rows(db, request)
    total = len(rows)
    selected = rows if request.page_size == "all" else rows[(request.page - 1) * request.page_size: request.page * request.page_size]
    payload, headers = _response_rows(selected, request)
    return {"headers": headers, "items": payload, "total": total, "unique_publication_count": unique_count,
            "scope": _scope_metadata(db, request),
            "row_mode": request.row_mode, "page": 1 if request.page_size == "all" else request.page, "page_size": request.page_size}


@router.post("/export/xlsx")
def export_xlsx(request: ReportRequest, db: Session = Depends(get_db)):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError as exc:
        raise HTTPException(503, "Excel export dependency is unavailable; install project requirements") from exc
    rows, unique_count = _build_rows(db, request)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Publications"
    scope = _scope_metadata(db, request)["label"]
    sheet.append(["Custom Publications Report"])
    sheet.append([f"Faculty scope: {scope} | Row mode: {request.row_mode.title()} | Unique publications: {unique_count} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"])
    headings = [_heading(request, field_id) for field_id in request.fields]
    sheet.append(headings)
    for cell in sheet[3]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
    for row in rows:
        values = []
        for field_id in request.fields:
            value = row.get(field_id, "")
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append(value)
        sheet.append(values)
    sheet.freeze_panes = "A4"
    from openpyxl.utils import get_column_letter
    sheet.auto_filter.ref = f"A3:{get_column_letter(len(headings))}{max(3, len(rows) + 3)}"
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(48, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
        for cell in column:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    name = f"custom-publications-report-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{name}"'})


class CitationRequest(ReportRequest):
    citation_style: Literal["IEEE", "APA", "HARVARD"] = "IEEE"
    include_needs_review: bool = False


def _citation_payload(db: Session, request: CitationRequest):
    request.row_mode = "PUBLICATION"
    rows, _ = _build_rows(db, request)
    results = []
    for row in rows:
        pub = row["_publication"]
        data = _citation_data(pub, row["_author_names"])
        results.append({"publication_id": pub.id, "formatted_citation": _citation(pub, row["_author_names"], request.citation_style),
                        "completeness_status": data["status"], "missing_fields": data["missing"],
                        "warnings": ["Original ordered bibliographic authors are incomplete or unavailable."] if "authors" in data["missing"] else []})
    if request.citation_style in {"APA", "HARVARD"}:
        results.sort(key=lambda item: item["formatted_citation"].casefold())
    included = [item for item in results if request.include_needs_review or item["completeness_status"] != "NEEDS_REVIEW"]
    return {"citation_style": request.citation_style, "items": included, "total_selected": len(results), "excluded_needs_review": len(results) - len(included),
            "complete": sum(item["completeness_status"] == "COMPLETE" for item in results),
            "incomplete": sum(item["completeness_status"] == "INCOMPLETE" for item in results),
            "needs_review": sum(item["completeness_status"] == "NEEDS_REVIEW" for item in results)}


@router.post("/citations")
def citations(request: CitationRequest, db: Session = Depends(get_db)):
    return _citation_payload(db, request)


def _citation_lines(payload):
    prefix = payload["citation_style"] == "IEEE"
    return [f"[{index}] {item['formatted_citation']}" if prefix else item["formatted_citation"]
            for index, item in enumerate(payload["items"], start=1)]


@router.post("/citations/export/docx")
def export_citation_docx(request: CitationRequest, db: Session = Depends(get_db)):
    try:
        from docx import Document
        from docx.shared import Inches, Pt
    except ImportError as exc:
        raise HTTPException(503, "Word export dependency is unavailable; install project requirements") from exc
    payload = _citation_payload(db, request)
    document = Document()
    document.add_heading("Publication Bibliography", level=1)
    document.add_paragraph(f"Style: {request.citation_style}. Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.")
    for line in _citation_lines(payload):
        paragraph = document.add_paragraph(line)
        paragraph.paragraph_format.left_indent = Inches(0.3)
        paragraph.paragraph_format.first_line_indent = Inches(-0.3)
        paragraph.paragraph_format.space_after = Pt(7)
    stream = BytesIO()
    document.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": 'attachment; filename="publication-bibliography.docx"'})


@router.post("/citations/export/pdf")
def export_citation_pdf(request: CitationRequest, db: Session = Depends(get_db)):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from xml.sax.saxutils import escape
    except ImportError as exc:
        raise HTTPException(503, "PDF export dependency is unavailable; install project requirements") from exc
    payload = _citation_payload(db, request)
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    reference = ParagraphStyle("Reference", parent=styles["BodyText"], leading=15, leftIndent=18, firstLineIndent=-18, spaceAfter=8)
    story = [Paragraph("Publication Bibliography", styles["Title"]), Paragraph(f"Style: {escape(request.citation_style)}", styles["BodyText"]), Spacer(1, 12)]
    story.extend(Paragraph(escape(line), reference) for line in _citation_lines(payload))
    document.build(story)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="publication-bibliography.pdf"'})


@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    return [{**columns(template), "config": _supported_template_config(template.config)}
            for template in db.scalars(select(PublicationReportTemplate).order_by(PublicationReportTemplate.name)).all()]


@router.post("/templates", status_code=201)
def create_template(data: TemplateInput, db: Session = Depends(get_db)):
    template = PublicationReportTemplate(name=data.name, description=data.description, config=data.config)
    db.add(template)
    db.commit()
    return {**columns(template), "config": template.config}


@router.put("/templates/{identity}")
def update_template(identity: int, data: TemplateInput, db: Session = Depends(get_db)):
    template = db.get(PublicationReportTemplate, identity)
    if not template:
        raise HTTPException(404, "Report template not found")
    if template.is_builtin:
        raise HTTPException(422, "Built-in templates cannot be changed")
    template.name, template.description, template.config = data.name, data.description, data.config
    db.commit()
    return {**columns(template), "config": template.config}


@router.delete("/templates/{identity}")
def delete_template(identity: int, db: Session = Depends(get_db)):
    template = db.get(PublicationReportTemplate, identity)
    if not template:
        raise HTTPException(404, "Report template not found")
    if template.is_builtin:
        raise HTTPException(422, "Built-in templates cannot be deleted")
    db.delete(template)
    db.commit()
    return {"deleted": identity}
