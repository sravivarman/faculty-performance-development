"""Upsert only the user-approved departmental Faculty Master roster."""
import json
from pathlib import Path

from sqlalchemy import select

from .db import SessionLocal, sqlite_database_path
from .models import Faculty
from .name_variants import normalize_person_name, prepare_variants

ROSTER_PATH = Path(__file__).resolve().parents[1] / "data" / "department_faculty.json"


def seed_faculty(db):
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    added = updated = 0
    for entry in roster:
        person = db.scalar(select(Faculty).where(Faculty.employee_id == entry["employee_id"]))
        if person is None:
            person = Faculty(employee_id=entry["employee_id"])
            db.add(person); added += 1
        else:
            updated += 1
        configured = {**(person.name_variant_strengths or {}),
                      **{normalize_person_name(v): "WEAK" for v in entry["weak_variants"]}}
        variants, strengths = prepare_variants((person.name_variants or []) + entry["name_variants"], configured)
        person.name = entry["name"]
        person.designation = entry["designation"]
        person.is_active = True
        person.name_variants = variants
        person.name_variant_strengths = strengths
        # ORCID, Scopus IDs, primary keys and activity links are preserved.
    db.commit()
    faculty = list(db.scalars(select(Faculty).order_by(Faculty.employee_id)))
    seeded = [p for p in faculty if p.employee_id in {r["employee_id"] for r in roster}]
    return {"added": added, "updated": updated, "requested_faculty_count": len(seeded), "faculty_master_count": len(faculty),
            "faculty_name_variant_count": sum(len(p.name_variants) for p in faculty),
            "seeded_name_variant_count": sum(len(p.name_variants) for p in seeded),
            "seeded_weak_variant_count": sum(v == "WEAK" for p in seeded for v in p.name_variant_strengths.values())}


if __name__ == "__main__":
    with SessionLocal() as db:
        print("SQLite database: " + sqlite_database_path(db))
        print(json.dumps(seed_faculty(db), indent=2))
