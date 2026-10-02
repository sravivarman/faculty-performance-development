"""Idempotent academic-year seed. Never creates fictitious faculty or papers."""
from datetime import date
from sqlalchemy import select
from .db import SessionLocal
from .models import AcademicYear


def seed():
    with SessionLocal() as db:
        for start_year in range(2024, 2029):
            start, end = date(start_year, 7, 1), date(start_year + 1, 6, 30)
            if not db.scalar(select(AcademicYear).where(AcademicYear.start_date <= end, AcademicYear.end_date >= start)):
                db.add(AcademicYear(name=f"{start_year}-{str(start_year + 1)[-2:]}", start_date=start, end_date=end))
        db.commit()


if __name__ == "__main__":
    seed()
    print("Academic-year seed complete; existing data preserved.")
