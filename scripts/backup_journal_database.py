"""Create and verify a SQLite online backup before journal import."""
import json
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--prefix', default='pre_journal_import')
args = parser.parse_args()
assert args.prefix in {'pre_journal_import', 'pre_bibtex_conference', 'pre_patent_import', 'pre_patent_types'}, 'Unsupported backup prefix'
source = root / 'data' / 'faculty.db'
target = root / 'data' / 'backups' / f'{args.prefix}_{datetime.now():%Y%m%d_%H%M%S}.db'
target.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True) as live:
    with sqlite3.connect(target) as backup:
        live.backup(backup)
with sqlite3.connect(f'{target.as_uri()}?mode=ro', uri=True) as check:
    assert check.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    assert not check.execute('PRAGMA foreign_key_check').fetchall()
    counts = {t: check.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
              for t in ['publications', 'publication_authors', 'faculty', 'students', 'evidence_files']}
print(json.dumps({'database_path': str(source), 'backup_path': str(target), 'verified': True, 'counts': counts}))
