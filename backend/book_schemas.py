import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .affiliations import PersonAffiliationInput
from .doi import normalize_doi
from .schemas import Input

WorkType = Literal["BOOK", "BOOK_CHAPTER"]


def normalize_isbn(value):
    if not value or not value.strip():
        return None
    number = re.sub(r"[\s-]", "", value).upper()
    valid10 = bool(re.fullmatch(r"\d{9}[\dX]", number))
    valid13 = bool(re.fullmatch(r"97[89]\d{10}", number))
    if valid10:
        valid10 = sum((10-i) * (10 if c == "X" else int(c)) for i, c in enumerate(number)) % 11 == 0
    if valid13:
        valid13 = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(number)) % 10 == 0
    if not (valid10 or valid13):
        raise ValueError("Enter a valid ISBN-10 or ISBN-13 (including its check digit), or leave ISBN blank")
    # Equivalent ISBN-10 and ISBN-13 editions match while display values stay intact.
    if valid10:
        prefix = "978" + number[:9]
        number = prefix + str((-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(prefix))) % 10)
    return number


class ContributorInput(PersonAffiliationInput):
    contributor_order: int = Field(ge=1)
    contributor_name: str = Field(min_length=1)
    role: Literal["AUTHOR", "EDITOR"] = "AUTHOR"
    source_metadata: dict | None = None


class BookInput(Input):
    work_type: WorkType
    title: str = Field(min_length=1)
    classification: Literal["INTERNATIONAL", "NATIONAL", "OTHER", "UNKNOWN"] | None = None
    volume: str | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=9999)
    metadata_source: Literal["MANUAL", "CROSSREF"] | None = None
    metadata_fetched_at: datetime | None = None
    raw_metadata_json: dict | None = None
    parent_book_title: str | None = None
    chapter_number: str | None = None
    isbn: str | None = None
    eisbn: str | None = None
    doi: str | None = None
    publisher: str = Field(min_length=1)
    publication_date: date
    edition: str | None = None
    page_range: str | None = None
    url: str | None = None
    remarks: str | None = None
    is_active: bool = True
    contributors: list[ContributorInput] = Field(min_length=1)
    duplicate_acknowledged: bool = False

    _doi = field_validator("doi")(normalize_doi)

    @model_validator(mode="after")
    def validate_work(self):
        normalize_isbn(self.isbn)
        normalize_isbn(self.eisbn)
        if self.work_type == "BOOK_CHAPTER":
            if not self.parent_book_title or not self.page_range:
                raise ValueError("A chapter requires its parent book title and page range")
            if not any(c.role == "AUTHOR" for c in self.contributors):
                raise ValueError("A chapter requires at least one chapter author")
        else:
            self.parent_book_title = self.chapter_number = self.page_range = None
        if sum(c.is_claiming_faculty for c in self.contributors) > 1:
            raise ValueError("At most one current-department faculty contributor may claim a work")
        if self.work_type == "BOOK_CHAPTER" and any(c.is_claiming_faculty and c.role != "AUTHOR" for c in self.contributors):
            raise ValueError("A chapter claimant must be a chapter author, not only a parent-book editor")
        for field in ("contributor_order",):
            values = [getattr(c, field) for c in self.contributors]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {field}")
        # A person may be both author and editor; duplicate rows in one role are invalid.
        for field in ("faculty_id", "student_id"):
            values = [(getattr(c, field), c.role) for c in self.contributors if getattr(c, field) is not None]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {field} for the same role")
        return self
