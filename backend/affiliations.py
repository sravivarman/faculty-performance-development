"""Shared identity and affiliation validation for research contributors."""
import os
from typing import Literal
from pydantic import model_validator
from .schemas import Input

INSTITUTION_NAME = "Vardhaman College of Engineering"
CURRENT_DEPARTMENT = os.getenv("CURRENT_DEPARTMENT", "EEE")
Scope = Literal["CURRENT_DEPARTMENT", "SAME_INSTITUTION_OTHER_DEPARTMENT", "EXTERNAL_INSTITUTION", "UNKNOWN"]

class PersonAffiliationInput(Input):
    person_type: Literal["FACULTY", "STUDENT", "EXTERNAL_PERSON", "UNKNOWN"] = "UNKNOWN"
    institution_scope: Scope = "UNKNOWN"
    faculty_id: int | None = None
    student_id: int | None = None
    department_name: str | None = None
    institution_name: str | None = None
    employee_or_roll_number: str | None = None
    is_claiming_faculty: bool = False

    @model_validator(mode="after")
    def identity(self):
        if self.faculty_id and (self.person_type != "FACULTY" or self.institution_scope != "CURRENT_DEPARTMENT" or self.student_id):
            raise ValueError("Faculty master links are only for current-department faculty")
        if self.student_id and (self.person_type != "STUDENT" or self.institution_scope != "CURRENT_DEPARTMENT" or self.faculty_id):
            raise ValueError("Student master links are only for current-department students")
        if self.is_claiming_faculty and not (self.person_type == "FACULTY" and self.institution_scope == "CURRENT_DEPARTMENT" and self.faculty_id):
            raise ValueError("Claimant must be a mapped current-department faculty contributor")
        if self.institution_scope in ("CURRENT_DEPARTMENT", "SAME_INSTITUTION_OTHER_DEPARTMENT"):
            self.institution_name = INSTITUTION_NAME
        if self.institution_scope == "CURRENT_DEPARTMENT":
            self.department_name = CURRENT_DEPARTMENT
        if self.institution_scope == "SAME_INSTITUTION_OTHER_DEPARTMENT":
            if not self.department_name:
                raise ValueError("Other-department contributors require a department name")
            if self.department_name.casefold() == CURRENT_DEPARTMENT.casefold():
                raise ValueError("Use Current Department for this department")
        if self.institution_scope == "EXTERNAL_INSTITUTION" and not self.institution_name:
            raise ValueError("External contributors require their institution/organization name")
        return self

