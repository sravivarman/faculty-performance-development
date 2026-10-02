import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from .schemas import Input

from .affiliations import CURRENT_DEPARTMENT, INSTITUTION_NAME, PersonAffiliationInput, Scope
from .patent_types import PatentType
PatentStatus = Literal["FILED", "PUBLISHED", "GRANTED", "REJECTED", "WITHDRAWN", "OTHER"]


def normalize_application_number(value):
    if not value or not value.strip():
        return None
    normalized = re.sub(r"[\s./_\-]+", "", unicodedata.normalize("NFKC", value).upper())
    if not normalized or not re.fullmatch(r"[A-Z0-9]+", normalized):
        raise ValueError("Application number may contain letters, digits, spaces, dots, slashes, underscores or hyphens")
    return normalized


class InventorInput(PersonAffiliationInput):
    inventor_order: int = Field(ge=1)
    inventor_name: str = Field(min_length=1)


class PatentInput(Input):
    title: str = Field(min_length=1)
    application_number: str | None = Field(default=None, max_length=200)
    patent_office: str = Field(min_length=1, max_length=150)
    country: str | None = None
    patent_type: PatentType
    filing_date: date | None = None
    publication_number: str | None = None
    publication_date: date | None = None
    grant_number: str | None = None
    grant_date: date | None = None
    current_status: PatentStatus = "FILED"
    applicant_assignee: str | None = None
    remarks: str | None = None
    is_claimable: bool = True
    is_active: bool = True
    inventors: list[InventorInput] = Field(default_factory=list)
    duplicate_acknowledged: bool = False
    status_note: str | None = None

    @model_validator(mode="after")
    def validate_patent(self):
        normalize_application_number(self.application_number)
        if self.publication_date and self.filing_date and self.publication_date < self.filing_date:
            raise ValueError("Publication date cannot precede filing date")
        if self.grant_date and self.filing_date and self.grant_date < self.filing_date:
            raise ValueError("Grant date cannot precede filing date")
        if self.grant_date and self.publication_date and self.grant_date < self.publication_date:
            raise ValueError("Grant date cannot precede publication date")
        if self.current_status == "PUBLISHED" and not self.publication_date:
            raise ValueError("Published status requires a publication date")
        if self.current_status == "GRANTED" and not self.grant_date:
            raise ValueError("Granted status requires a grant date")
        if self.grant_date and self.current_status in ("FILED", "PUBLISHED"):
            raise ValueError("A recorded grant requires Granted or a later terminal/other status")
        if self.publication_date and self.current_status == "FILED":
            raise ValueError("A recorded publication requires Published or a later status")
        claims = sum(i.is_claiming_faculty for i in self.inventors)
        faculty = any(i.person_type == "FACULTY" and i.institution_scope == "CURRENT_DEPARTMENT" for i in self.inventors)
        if not self.is_claimable and claims:
            raise ValueError("A non-claimable patent cannot have a claimant")
        if self.is_claimable and faculty and not claims:
            raise ValueError("Select at least one mapped current-department faculty claimant or mark non-claimable")
        for field in ("inventor_order", "faculty_id", "student_id"):
            values = [getattr(i, field) for i in self.inventors if getattr(i, field) is not None]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {field} in inventor list")
        return self
