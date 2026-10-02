"""Read-only verification of every exported report row and summary count."""
import csv
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from openpyxl import load_workbook

report = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
xlsx = Path(sys.argv[2])
book = load_workbook(xlsx, read_only=True, data_only=True)
sheet = book['Import rows']
rows = list(sheet.iter_rows(min_row=4, max_row=141, min_col=1, max_col=21, values_only=True))
assert len(rows) == len(report['rows']) == 138
for expected, actual in zip(report['rows'], rows):
    for (key, value), cell in zip(expected.items(), actual):
        if key == 'publication_date' and value:
            assert isinstance(cell, (datetime, date))
            cell = cell.date().isoformat() if isinstance(cell, datetime) else cell.isoformat()
        if isinstance(value, list):
            value = ' | '.join(str(v) for v in value) or None
        assert cell == value, (expected['excel_row'], key, value, cell)
summary = book['Summary']
assert summary['B5'].value == report['validation']['stored_historical_publications'] == 125
assert summary['B10'].value == 138
assert sum(summary.cell(r,3).value for r in range(22,41)) == 125
book.close()
with (Path(sys.argv[1]).parent / 'journal-import.csv').open(encoding='utf-8-sig', newline='') as handle:
    csv_rows = list(csv.DictReader(handle))
assert len(csv_rows) == 138
assert [int(r['excel_row']) for r in csv_rows] == [r['excel_row'] for r in report['rows']]
assert csv_rows[84]['status'] == 'SKIPPED_UNRESOLVED_CLAIMANT'
assert hashlib.sha256(Path(report['source']['source']).read_bytes()).hexdigest() == report['source']['source_sha256']
print('Verified all 138 XLSX and CSV rows; summary/claimant totals 125; source workbook unchanged.')
