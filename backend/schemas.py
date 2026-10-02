from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .doi import normalize_doi, normalize_orcid
from .name_variants import prepare_variants

PublicationType = Literal["JOURNAL", "CONFERENCE", "OTHER"]
Indexing = Literal["SCOPUS", "WEB_OF_SCIENCE", "SCI", "SCIE", "ESCI", "UGC_CARE", "OTHER", "NONE", "UNKNOWN"]


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


class FacultyInput(Input):
    employee_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    designation: str | None = None
    orcid: str | None = None
    scopus_author_id: str | None = None
    name_variants: list[str] = Field(default_factory=list)
    name_variant_strengths: dict[str, Literal["STRONG", "WEAK"]] | None = None
    is_active: bool = True
    _orcid = field_validator("orcid")(normalize_orcid)

    @model_validator(mode="after")
    def variants(self):
        values, strengths = prepare_variants(self.name_variants, self.name_variant_strengths)
        self.name_variants = values
        if self.name_variant_strengths is not None:
            self.name_variant_strengths = strengths
        return self


class StudentInput(Input):
    roll_number: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    batch: str | None = None
    program: str | None = None
    year_of_study: int | None = Field(default=None, ge=1, le=10)
    name_variants: list[str] = Field(default_factory=list)
    is_active: bool = True


class YearInput(Input):
    name: str = Field(min_length=1, max_length=30)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def dates(self):
        if self.start_date.day != 1 or self.end_date <= self.start_date:
            raise ValueError("Academic year must start on the first of a month")
        from .periods import add_months
        from datetime import timedelta
        if self.end_date != add_months(self.start_date, 12) - timedelta(days=1):
            raise ValueError("Academic year must span exactly 12 months")
        return self


class AuthorInput(Input):
    author_order: int = Field(ge=1)
    author_name_from_source: str = Field(min_length=1)
    given_name_from_source: str | None = None
    family_name_from_source: str | None = None
    orcid_from_source: str | None = None
    affiliation_from_source: list[str] = Field(default_factory=list)
    person_type: Literal["FACULTY", "STUDENT", "EXTERNAL", "UNKNOWN"] = "UNKNOWN"
    faculty_id: int | None = None
    student_id: int | None = None
    is_internal: bool = False
    is_claiming_faculty: bool = False
    is_corresponding_author: bool = False
    is_first_author: bool = False
    matching_status: Literal["UNMATCHED", "CONFIRMED", "EXACT", "SUGGESTED"] = "UNMATCHED"
    matching_confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def identity(self):
        if self.person_type == "FACULTY":
            if not self.faculty_id or self.student_id:
                raise ValueError("Faculty authors require faculty_id only")
        elif self.person_type == "STUDENT":
            if not self.student_id or self.faculty_id:
                raise ValueError("Student authors require student_id only")
        elif self.faculty_id or self.student_id:
            raise ValueError("External/unknown authors cannot link internal people")
        self.is_internal = self.person_type in ("FACULTY", "STUDENT")
        if self.is_claiming_faculty and self.person_type != "FACULTY":
            raise ValueError("Claimant must be an identified internal faculty author")
        if self.matching_status == "SUGGESTED" and self.is_internal:
            raise ValueError("Suggested matches must be confirmed before mapping")
        return self


class PublicationInput(Input):
    academic_year_id: int | None = None
    doi: str | None = None
    title: str = Field(min_length=1)
    publication_type: PublicationType = "OTHER"
    journal_conference_name: str | None = None
    conference_name: str | None = None
    proceedings_title: str | None = None
    conference_start_date: date | None = None
    conference_end_date: date | None = None
    conference_location: str | None = None
    conference_organizer: str | None = None
    publisher: str | None = None
    publication_date: date
    online_publication_date: date | None = None
    print_publication_date: date | None = None
    volume: str | None = None
    issue: str | None = None
    pages_or_article_number: str | None = None
    issn: str | None = None
    eissn: str | None = None
    isbn: str | None = None
    url: str | None = None
    indexing: list[Indexing] = Field(default_factory=list)
    classification: Literal["INTERNATIONAL", "NATIONAL", "OTHER", "UNKNOWN"] = "UNKNOWN"
    impact_factor: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    quartile: Literal["Q1", "Q2", "Q3", "Q4", "NOT_APPLICABLE", "UNKNOWN"] | None = None
    remarks: str | None = None
    metadata_source: Literal["MANUAL", "CROSSREF", "BIBTEX", "BIBTEX_PLUS_DOI"] = "MANUAL"
    source_type: Literal["MANUAL", "DOI", "BIBTEX", "BIBTEX_PLUS_DOI", "HISTORICAL_EXCEL"] = "MANUAL"
    raw_bibtex: str | None = None
    metadata_fetched_at: datetime | None = None
    raw_metadata_json: dict | None = None
    is_claimable: bool = True
    is_active: bool = True
    authors: list[AuthorInput] = Field(default_factory=list)
    duplicate_acknowledged: bool = False
    _doi = field_validator("doi")(normalize_doi)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        if value and not value.lower().startswith(("https://", "http://")):
            raise ValueError("URL must use http or https")
        return value

    @model_validator(mode="after")
    def claims(self):
        if self.publication_type == "CONFERENCE" and not self.journal_conference_name:
            self.journal_conference_name = self.proceedings_title or self.conference_name
        if self.conference_start_date and self.conference_end_date and self.conference_end_date < self.conference_start_date:
            raise ValueError("Conference end date cannot precede its start date")
        claims = sum(a.is_claiming_faculty for a in self.authors)
        if claims > 1:
            raise ValueError("Only one faculty may claim a publication")
        if not self.is_claimable and claims:
            raise ValueError("A non-claimable publication cannot have a claimant")
        if self.is_claimable and claims != 1:
            raise ValueError("Select exactly one claiming faculty or mark non-claimable")
        if self.source_type in {"BIBTEX", "BIBTEX_PLUS_DOI"}:
            if self.publication_type == "OTHER":
                raise ValueError("Review the BibTeX type and choose Journal or Conference")
            if not self.raw_bibtex:
                raise ValueError("BibTeX publications require their original entry")
            if self.is_claimable and claims != 1:
                raise ValueError("Select one internal faculty author as the claimant")
        for field in ("author_order", "faculty_id", "student_id"):
            values = [getattr(a, field) for a in self.authors if getattr(a, field) is not None]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {field} in author list")
        self.indexing = list(dict.fromkeys(self.indexing))
        if len(self.indexing) > 1 and set(self.indexing) & {"NONE", "UNKNOWN"}:
            raise ValueError("NONE and UNKNOWN cannot be combined with other indexing categories")
        return self
