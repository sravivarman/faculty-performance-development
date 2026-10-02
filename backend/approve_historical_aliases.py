"""Add approved aliases atomically after checking all faculty for conflicts."""
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from .db import SessionLocal, sqlite_database_path
from .models import Faculty
from .name_variants import normalize_person_name, prepare_variants

ALIASES_PATH = Path(__file__).resolve().parents[1] / "data" / "historical_faculty_aliases.json"


def approve_aliases(db, approvals=None):
    approvals = approvals if approvals is not None else json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    faculty = list(db.scalars(select(Faculty).order_by(Faculty.employee_id)))
    by_employee = {p.employee_id: p for p in faculty}
    missing = set(approvals) - set(by_employee)
    if missing:
        raise ValueError(f"Missing Faculty Master IDs; no records changed: {sorted(missing)}")
    planned = {}
    for person in faculty:
        additions = approvals.get(person.employee_id, [])
        strengths = {**(person.name_variant_strengths or {}), **{normalize_person_name(v): "STRONG" for v in additions}}
        planned[person.employee_id] = prepare_variants(person.name_variants + additions, strengths)
    # Include inactive faculty and canonical names in conflict detection. No
    # database changes occur until every approved alias has exactly one owner.
    owners = defaultdict(set)
    for person in faculty:
        owners[normalize_person_name(person.name)].add(person.employee_id)
        for variant in planned[person.employee_id][0]:
            owners[normalize_person_name(variant)].add(person.employee_id)
    conflicts = {normalize_person_name(v): sorted(owners[normalize_person_name(v)])
                 for variants, _ in planned.values() for v in variants if len(owners[normalize_person_name(v)]) != 1}
    if conflicts:
        raise ValueError("Alias conflicts; no records changed: " + json.dumps(conflicts, ensure_ascii=False))
    before = sum(len(p.name_variants) for p in faculty)
    for employee in approvals:
        person = by_employee[employee]
        person.name_variants, person.name_variant_strengths = planned[employee]
    db.commit()
    return {"faculty_master_count": len(faculty), "variant_count_before": before,
            "variant_count": sum(len(p.name_variants) for p in faculty),
            "added_normalized_variants": sum(len(p.name_variants) for p in faculty) - before,
            "alias_conflicts": 0}


if __name__ == "__main__":
    with SessionLocal() as db:
        print("SQLite database: " + sqlite_database_path(db))
        print(json.dumps(approve_aliases(db), indent=2))
