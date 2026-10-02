"""Verify additive publication migration against a read-only pre-migration backup."""
import json
import sqlite3
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
backup = Path(sys.argv[1]).resolve()
with sqlite3.connect(f'{backup.as_uri()}?mode=ro',uri=True) as before, sqlite3.connect(root/'data'/'faculty.db') as live:
    tables=[r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")]
    counts={}
    for table in tables:
        fields=[r[1] for r in before.execute(f'PRAGMA table_info("{table}")')]
        names=','.join('"'+field+'"' for field in fields)
        old=before.execute(f'SELECT {names} FROM "{table}" ORDER BY id').fetchall()
        new=live.execute(f'SELECT {names} FROM "{table}" ORDER BY id').fetchall()
        assert old == new, f'Existing {table} data changed'
        counts[table]=len(new)
    assert live.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    assert live.execute('PRAGMA foreign_key_check').fetchall() == []
    assert live.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'b85dc163ab92'
    assert live.execute("SELECT count(*) FROM publications WHERE source_type='HISTORICAL_EXCEL'").fetchone()[0] == 125
    result={'database_path':str(root/'data'/'faculty.db'),'backup_path':str(backup),'integrity':'ok',
            'all_existing_rows_and_fields_preserved':True,'counts':counts,
            'historical_publications_preserved':125,
            'source_types':dict(live.execute('SELECT source_type,count(*) FROM publications GROUP BY source_type'))}
    folder=root/'reports'/'bibtex-conference'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'migration-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
