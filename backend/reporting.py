from datetime import date

from fastapi import HTTPException


def validate_date_range(from_date: date | None, to_date: date | None, *, required=True):
    """The single inclusive date-range contract used by reports and drill-downs."""
    if from_date is None and to_date is None and not required:
        return None
    if from_date is None or to_date is None:
        raise HTTPException(422, "From Date and To Date are both required")
    if from_date > to_date:
        raise HTTPException(422, "From Date must be on or before To Date")
    return from_date, to_date


def within(value: date | None, from_date: date, to_date: date):
    return value is not None and from_date <= value <= to_date


# Reporting-date conventions for future modules; no duplicate activity records.
REPORTING_DATES = {
    "publication": "publication_date", "book": "publication_date",
    "training": "end_date", "certification": "completion_date",
    "patent_filed": "filing_date", "patent_published": "publication_date", "patent_granted": "grant_date",
    "proposal_submitted": "submission_date", "proposal_sanctioned": "sanction_date",
    "proposal_started": "project_start_date", "consultancy_started": "start_date",
    "consultancy_completed": "end_date", "consultancy_revenue": "received_date",
}
