"""Controlled, reproducible department CY2026 patent import. Dry run by default."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import select, text
from backend.db import SessionLocal, ROOT, sqlite_database_path
from backend.models import Faculty, Patent
from backend.name_variants import normalize_person_name
from backend.patent_schemas import PatentInput, normalize_application_number
from backend.patent_services import save_patent, patent_dict

SOURCE = ROOT / 'data' / 'historical_patents_2026.json'
PROVENANCE = 'Department Patents Summary — CY 2026'
# Explicit identities supplied in the verified import specification. Canonical
# Master identity is checked too; these are not fuzzy guesses or new aliases.
IDENTITIES = {
    'VCE801': ('B Raja Gopal Reddy', ['B Raja Gopal Reddy', 'B Rajagopal Reddy', 'B Raj Gopal Reddy']),
    'VCE087': ('N Srinivas', ['Nakka Srinivas', 'N Srinivas']),
    'VCE1009': ('A Ananda Kumar', ['A Ananda Kumar']),
    'VCE1011': ('T Anuradha Devi', ['T Anuradha Devi', 'Anuradha Devi Tellapati']),
    'VCE1199': ('Fatima Unnisa', ['Fatima Unnisa']),
    'VCE792': ('D Revathi', ['D Revathi']),
    'VCE1496': ('Muruga Perumal', ['K Murugaperumal', 'Murugaperumal']),
    'VCE306': ('A Rama Krishna', ['Adiraju Ramakrishna']),
    'VCE1430': ('G Indirarani', ['Indirarani Guntu']),
    'VCE967': ('Patil Mounica', ['Patil Mounica', 'P Mounica']),
    'VCE1074': ('B Mohan', ['Bukya Mohan', 'B Mohan']),
    'VCE1127': ('S Ravivarman', ['S Ravivarman']),
    'VCE1172': ('N Karuppiah', ['N Karuppiah', 'N Karuppaiah']),
    'VCE1422': ('S Vinod Reddy', ['S Vinod Reddy']),
    'VCE1837': ('B Balakrishna', ['Bandi Balakrishna']),
}


def reconcile(db, source):
    faculty = db.scalars(select(Faculty)).all()
    candidates = {}
    def add(name, person, reason):
        candidates.setdefault(normalize_person_name(name), {})[person.id] = (person, reason)
    for person in faculty:
        add(person.name, person, 'CANONICAL')
        for alias in person.name_variants:
            if person.name_variant_strengths.get(normalize_person_name(alias), 'STRONG') == 'STRONG':
                add(alias, person, 'STRONG_VARIANT')
    for employee, (canonical, aliases) in IDENTITIES.items():
        persons = [p for p in faculty if p.employee_id == employee and normalize_person_name(p.name) == normalize_person_name(canonical)]
        if len(persons) == 1:
            for alias in aliases:
                key = normalize_person_name(alias)
                if persons[0].id not in candidates.get(key, {}):
                    add(alias, persons[0], 'SOURCE_EMPLOYEE_ID_VERIFIED')
    result = []
    seen = set()
    for record in source:
        kind = record['type'].strip().upper()
        number = normalize_application_number(record['number'])
        if number in seen:
            raise ValueError('Duplicate identifier in source: '+record['number'])
        seen.add(number)
        existing = db.scalar(select(Patent).where(Patent.normalized_application_number == number))
        inventors, matching = [], []
        for order, inventor in enumerate(record['inventors'], 1):
            hits = candidates.get(normalize_person_name(inventor['name']), {}) if inventor['department'] else {}
            if len(hits) > 1:
                raise ValueError('AMBIGUOUS: '+inventor['name']+' matches '+', '.join(p.employee_id for p,_ in hits.values()))
            person, reason = next(iter(hits.values())) if hits else (None, None)
            matching.append({'source_name': inventor['name'], 'classification': 'DEPARTMENT' if inventor['department'] else 'EXTERNAL / OTHER',
                             'faculty_name': person.name if person else None, 'employee_id': person.employee_id if person else None,
                             'match_source': reason or ('CURRENT_DEPARTMENT_UNMATCHED' if inventor['department'] else 'EXTERNAL / OTHER')})
            inventors.append({'inventor_order': order, 'inventor_name': inventor['name'],
                              'person_type': 'FACULTY' if person else 'UNKNOWN' if inventor['department'] else 'EXTERNAL_PERSON',
                              'institution_scope': 'CURRENT_DEPARTMENT' if inventor['department'] else 'UNKNOWN',
                              'faculty_id': person.id if person else None, 'is_claiming_faculty': bool(person)})
        iso = lambda value: datetime.strptime(value, '%d/%m/%Y').date().isoformat() if value else None
        payload = {'title': record['title'], 'application_number': record['number'], 'patent_type': kind,
                   'patent_office': 'Not specified in source', 'country': None, 'filing_date': None,
                   'publication_date': iso(record['publication_date']), 'grant_date': iso(record['grant_date']),
                   'current_status': 'GRANTED' if record['grant_date'] else 'PUBLISHED', 'inventors': inventors,
                   'remarks': PROVENANCE+'; source column: Patent Number; identifier preserved in generic application_number field. '
                              'Office, country, filing date and external affiliations were not supplied. '
                              'UNKNOWN/current-department inventors are CURRENT_DEPARTMENT_UNMATCHED; external person/UNKNOWN scope means external affiliation unspecified.'}
        validated = PatentInput.model_validate(payload)
        if existing:
            current = patent_dict(existing, db)
            # Existing records are skipped only when import values agree. Never
            # overwrite verified history or silently reconcile a conflict.
            for key in ('title', 'application_number', 'patent_type', 'publication_date', 'grant_date', 'current_status'):
                if str(current[key]) != str(getattr(validated, key)):
                    raise ValueError('Existing patent conflicts with source: '+record['number']+' / '+key)
            signatures = lambda rows: [(i['inventor_order'],i['inventor_name'],i['person_type'],i['institution_scope'],i['faculty_id'],i['is_claiming_faculty']) for i in rows]
            if signatures(current['inventors']) != signatures(inventors):
                raise ValueError('Existing inventor/claim relationships require manual reconciliation: '+record['number'])
        result.append({'identifier': record['number'], 'title': record['title'], 'existing_id': existing.id if existing else None,
                       'type': kind, 'status': validated.current_status, 'inventor_count': len(inventors),
                       'claimant_count': sum(i['is_claiming_faculty'] for i in inventors), 'matching': matching,
                       'payload': validated.model_dump(mode='json')})
    return result


def run(db, source, apply=False):
    if apply:
        db.execute(text('BEGIN IMMEDIATE'))
    rows = reconcile(db, source)
    for row in rows:
        if apply and not row['existing_id']:
            row['inserted_id'] = save_patent(db, PatentInput.model_validate(row['payload']), commit=False).id
    if apply:
        db.commit()
    return {'database': sqlite_database_path(db), 'mode': 'IMPORT' if apply else 'DRY_RUN', 'ambiguous': 0,
            'source_patents': len(rows), 'inserted': sum('inserted_id' in r for r in rows),
            'existing': sum(bool(r['existing_id']) for r in rows), 'records': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        report = run(db, json.loads(SOURCE.read_text(encoding='utf-8')), args.apply)
    path = Path(args.report); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='records'}))
