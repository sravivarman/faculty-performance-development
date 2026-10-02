"""Read-only journal claimant reconciliation; this module never saves publications."""
import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from .db import SessionLocal, sqlite_database_path
from .matching import reconcile_faculty_name
from .models import Faculty


def reconcile(source, faculty):
    groups = {}
    for row in source["rows"]:
        groups.setdefault(row["author_value"], []).append(row)
    rows = []
    for value, source_rows in sorted(groups.items(), key=lambda item: item[0].casefold()):
        rows.append({"excel_author_value": value, **reconcile_faculty_name(value, faculty), "excel_rows": len(source_rows),
                     "source_rows": [r["excel_row"] for r in source_rows]})
    counts = Counter(r["match_source"] for r in rows)
    summary = {"faculty_master_count": len(faculty), "faculty_name_variant_count": sum(len(p.name_variants) for p in faculty),
               "total_journal_rows": len(source["rows"]), "unique_excel_claimant_values": len(rows),
               **{key: counts[source] for key, source in (("canonical_matches", "CANONICAL"), ("strong_variant_matches", "STRONG_VARIANT"),
                ("weak_variant_matches", "WEAK_VARIANT"), ("unmatched_values", "UNMATCHED"), ("ambiguous_values", "AMBIGUOUS"))},
               "rows_requiring_review": sum(r["excel_rows"] for r in rows if r["requires_review"]),
               "blank_claimant_rows": sum(not r["author_value"].strip() for r in source["rows"]),
               "missing_title_rows": sum(not r["has_title"] for r in source["rows"]),
               "grouped_row_total": sum(r["excel_rows"] for r in rows)}
    if summary["grouped_row_total"] != summary["total_journal_rows"]:
        raise RuntimeError("Claimant reconciliation lost rows")
    return {"source": {k: v for k, v in source.items() if k != "rows"}, "summary": summary, "claimants": rows}


def write_report(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "claimant-reconciliation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    columns = ["Excel Author Value", "Normalized Excel Value", "Matched Faculty", "Employee ID", "Match Source", "Number of Excel Rows", "Requires Review", "Excel Row Numbers", "Candidates"]
    with (directory / "claimant-reconciliation.csv").open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output); writer.writerow(columns)
        for r in report["claimants"]:
            writer.writerow([r["excel_author_value"], r["normalized_value"], r["matched_faculty"] or "", r["employee_id"] or "",
                             r["match_source"], r["excel_rows"], "Yes" if r["requires_review"] else "No", ", ".join(map(str,r["source_rows"])),
                             "; ".join(f'{c["employee_id"]}: {c["name"]}' for c in r["candidates"])])
    def cell(value):
        return str(value or "—").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# Journal claimant reconciliation", "", f'Source: `{report["source"]["source"]}` · Sheet: `{report["source"]["sheet"]}`',
             "", "Authors is the departmental claimant field, not the complete publication author list. No publications have been imported.",
             "", "## Summary", "", "| Measure | Count |", "| --- | ---: |"]
    if "database_path" in report:
        lines[4:4] = [f'SQLite database: `{report["database_path"]}`', "", f'Generated at (UTC): `{report["generated_at"]}`', ""]
    lines.extend(f'| {k.replace("_", " ").title()} | {v} |' for k, v in report["summary"].items())
    lines += ["", f'Row conservation: **{report["summary"]["grouped_row_total"]} grouped rows = {report["summary"]["total_journal_rows"]} nonempty journal rows**.',
              "", "Weak and ambiguous matches require manual review. Unmatched values remain unresolved; no new faculty are created from Excel names.",
              "", "## Unique claimant values", "", "| Excel Author Value | Normalized Excel Value | Matched Faculty | Employee ID | Match Source | Number of Excel Rows | Requires Review |", "| --- | --- | --- | --- | --- | ---: | --- |"]
    for r in report["claimants"]:
        lines.append("| " + " | ".join(cell(v) for v in [r["excel_author_value"], r["normalized_value"], r["matched_faculty"], r["employee_id"],
                                                        r["match_source"], r["excel_rows"], "Yes" if r["requires_review"] else "No"]) + " |")
    (directory / "claimant-reconciliation.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("excel")
    parser.add_argument("--reader-python", required=True, help="Python executable with openpyxl available")
    parser.add_argument("--sheet")
    parser.add_argument("--output", default="reports/journal-claimants")
    args = parser.parse_args()
    reader = Path(__file__).resolve().parents[1] / "scripts" / "read_journal_claimants.py"
    command = [args.reader_python, str(reader), args.excel]
    if args.sheet:
        command += ["--sheet", args.sheet]
    source = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    with SessionLocal() as db:
        database_path = sqlite_database_path(db)
        print("SQLite database: " + database_path)
        faculty = list(db.scalars(select(Faculty).order_by(Faculty.name)))
        report = reconcile(source, faculty)
        report.update(database_path=database_path, generated_at=datetime.now(timezone.utc).isoformat())
    write_report(report, Path(args.output))
    print(json.dumps(report["summary"], indent=2))
