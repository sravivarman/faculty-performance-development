"""One-time, audited journal import through the existing metadata/save services.

No faculty creation, evidence creation, fuzzy mapping, or existing publication updates.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
import re
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from sqlalchemy import select

from .db import SessionLocal, sqlite_database_path
from .doi import normalize_doi
from .matching import match_author, reconcile_faculty_name
from .metadata import CrossrefProvider, MetadataError
from .models import Faculty, Publication, Student
from .schemas import PublicationInput
from .services import department_kpis, save_publication

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'data' / 'faculty.db'


class ImportConflict(RuntimeError):
    """A conflict requires stopping rather than choosing an identity."""


def historical_doi(value):
    # Embedded whitespace and a punctuation full stop are common pasted URL artifacts.
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Missing DOI')
    # Remove copied UI labels only at their explicit boundaries, never arbitrary
    # suffix characters from an identifier. Crossref still verifies the result.
    value = re.sub(r'\s*Digital\s*Object\s*Identifier\s*\(DOI\)\s*$', '', value, flags=re.I)
    value = re.sub(r'[\r\n]+\s*PDF\s*$', '', value, flags=re.I)
    value = re.sub(r'^\s*doi\s*:\s*', '', value, flags=re.I)
    return normalize_doi(re.sub(r'\s+', '', value).rstrip('.'))


def kpi_values(row):
    mapping = {'sci': 'SCI', 'scie': 'SCIE', 'scopus': 'SCOPUS', 'web of science': 'WEB_OF_SCIENCE',
               'web_of_science': 'WEB_OF_SCIENCE', 'esci': 'ESCI', 'ugc care': 'UGC_CARE',
               'ugc_care': 'UGC_CARE', 'none': 'NONE', 'unknown': 'UNKNOWN', 'other': 'OTHER'}
    indexing = []
    for token in re.split(r'[\n,;/]+', str(row.get('Indexing') or '')):
        if not token.strip():
            continue
        key = token.strip().casefold()
        if key not in mapping:
            raise ValueError('INDEXING_REVIEW: ' + token)
        indexing.append(mapping[key])
    indexing = list(dict.fromkeys(indexing))
    if len(indexing) > 1 and set(indexing) & {'NONE', 'UNKNOWN'}:
        raise ValueError('INDEXING_REVIEW: incompatible indexing values')
    factor = row.get('Impact Factor')
    if factor is None or (isinstance(factor, str) and not factor.strip()):
        factor = None
    else:
        try:
            if isinstance(factor, bool):
                raise ValueError()
            factor = float(factor)
            if not math.isfinite(factor) or factor < 0:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError('INVALID_IMPACT_FACTOR: ' + str(row.get('Impact Factor')))
    quartile = str(row.get('Quartile') or '').strip().upper() or None
    if quartile is not None and quartile not in {'Q1', 'Q2', 'Q3', 'Q4'}:
        raise ValueError('INVALID_QUARTILE: ' + quartile)
    return {'indexing': indexing, 'impact_factor': factor, 'quartile': quartile}


class CachedMetadata:
    def __init__(self, directory, provider=None, sleep=time.sleep):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.provider = provider or CrossrefProvider()
        self.sleep = sleep
        self.memory = {}

    def fetch(self, doi):
        key = hashlib.sha256(doi.encode()).hexdigest()
        path = self.directory / (key + '.json')
        if doi in self.memory:
            return copy.deepcopy(self.memory[doi])
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            if normalize_doi(data['doi']) != doi:
                raise MetadataError('Cached DOI mismatch')
            self.memory[doi] = data
            return copy.deepcopy(data)
        for attempt in range(4):
            try:
                data = self.provider.fetch_by_doi(doi)
                if normalize_doi(data['doi']) != doi:
                    raise MetadataError('Returned DOI does not match requested DOI')
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                self.memory[doi] = data
                return copy.deepcopy(data)
            except MetadataError as exc:
                cause = exc.__cause__
                status = cause.response.status_code if isinstance(cause, httpx.HTTPStatusError) else None
                temporary = isinstance(cause, httpx.RequestError) or status == 429 or (status is not None and status >= 500)
                if not temporary or attempt == 3:
                    raise
                delay = 2 ** (attempt + 1)
                if status == 429:
                    retry = cause.response.headers.get('Retry-After')
                    if retry:
                        try:
                            delay = max(delay, float(retry))
                        except ValueError:
                            try:
                                delay = max(delay, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds())
                            except (ValueError, TypeError):
                                pass
                print(f'Retrying {doi}: HTTP {status or "network"}, delay {delay:.0f}s', flush=True)
                self.sleep(delay)


def build_publication(row, metadata, claimant, faculty, students):
    data = copy.deepcopy(metadata)
    warnings = []
    data['doi'] = historical_doi(row['DoI'])
    data['title'] = data.get('title') or str(row['Title of the paper'] or '').strip()
    data['journal_conference_name'] = data.get('journal_conference_name') or row['Name of the Journal']
    if not data.get('publication_date'):
        # Only an actual calendar date stored in Excel is allowed. Month/year text
        # cannot be converted into an invented day. Preserve provenance explicitly.
        try:
            data['publication_date'] = date.fromisoformat(str(row['Month and Year']).split('T')[0]).isoformat()
        except (TypeError, ValueError):
            raise ValueError('PUBLICATION_DATE_REVIEW: no exact DOI or Excel date')
        warnings.append('Publication date uses the calendar date stored in Excel Month and Year; DOI has no exact date.')
    mapped = [match_author(a, faculty, students) for a in data.get('authors', [])]
    claim_authors = [a for a in mapped if a.get('person_type') == 'FACULTY' and a.get('faculty_id') == claimant.id and a.get('matching_status') == 'EXACT']
    if len(claim_authors) != 1:
        raise ValueError('CLAIMANT_NOT_IN_DOI_AUTHORS: expected exactly one conservative author match; found ' + str(len(claim_authors)))
    claim_authors[0]['is_claiming_faculty'] = True
    # Duplicate internal identities cannot be chosen arbitrarily; review the row.
    for key in ('faculty_id', 'student_id'):
        ids = [a.get(key) for a in mapped if a.get(key)]
        if len(ids) != len(set(ids)):
            raise ValueError('AUTHOR_IDENTITY_REVIEW: multiple DOI authors match the same master record')
    for a in mapped:
        if not a.get('is_internal'):
            # An affiliation alone does not establish external/institution identity.
            a.update(person_type='UNKNOWN', matching_status='UNMATCHED', matching_confidence=None)
    data['authors'] = mapped
    data.update(kpi_values(row), is_claimable=True, is_active=True, source_type='HISTORICAL_EXCEL')
    data['remarks'] = f'Historical journal import: Journal Excel row {row["excel_row"]}; claimant/KPIs from Excel.'
    if warnings:
        data['remarks'] += ' ' + ' '.join(warnings)
    return PublicationInput(**data), warnings


def process_row(db, row, claimant, faculty, students, fetch):
    result = {'excel_row': row['excel_row'], 's_no': row['S.No'], 'normalized_doi': None,
              'excel_title': row['Title of the paper'], 'stored_doi_title': None,
              'excel_claimant': row['Authors'], 'matched_faculty': claimant.name if claimant else None,
              'employee_id': claimant.employee_id if claimant else None, 'claimant_found_in_doi_authors': None,
              'excel_journal': row['Name of the Journal'], 'doi_journal': None, 'publication_date': None,
              'excel_indexing': row['Indexing'], 'excel_impact_factor': row['Impact Factor'], 'excel_quartile': row['Quartile'],
              'indexing': None, 'impact_factor': None, 'quartile': None, 'publication_id': None, 'status': None, 'warnings_errors': []}
    if row['excel_row'] == 86 and row['Authors'].strip() == 'Archana Chittari':
        result['status'] = 'SKIPPED_UNRESOLVED_CLAIMANT'
        result['warnings_errors'] = ['Archana Chittari — Excel row 86 — not imported']
        return result
    try:
        try:
            doi = historical_doi(row['DoI'])
        except ValueError as exc:
            result.update(status='INVALID_DOI', warnings_errors=[str(exc)])
            return result
        result['normalized_doi'] = doi
        # Inspect all stored DOI representations, including legacy URL forms.
        existing = []
        for pub in db.scalars(select(Publication).where(Publication.doi.is_not(None))):
            try:
                if historical_doi(pub.doi) == doi:
                    existing.append(pub)
            except ValueError:
                continue
        if len(existing) > 1:
            raise ImportConflict('Multiple existing publications have this normalized DOI; stop for conflict review')
        if existing:
            pub = existing[0]
            result.update(status='DUPLICATE', publication_id=pub.id, stored_doi_title=pub.title,
                          publication_date=pub.publication_date.isoformat(), indexing=pub.indexing,
                          impact_factor=pub.impact_factor, quartile=pub.quartile,
                          warnings_errors=['Existing publication preserved without changes.'])
            return result
        if claimant is None:
            raise ImportConflict('Missing verified claimant mapping')
        try:
            values = kpi_values(row)
        except ValueError as exc:
            result.update(status=str(exc).split(':')[0], warnings_errors=[str(exc)])
            return result
        result.update(values)
        try:
            metadata = fetch(doi)
        except MetadataError as exc:
            cause = exc.__cause__
            detail = f' HTTP {cause.response.status_code}' if isinstance(cause, httpx.HTTPStatusError) else ''
            result.update(status='DOI_FETCH_FAILED', warnings_errors=[str(exc) + detail])
            return result
        result.update(stored_doi_title=metadata.get('title'), doi_journal=metadata.get('journal_conference_name'),
                      publication_date=metadata.get('publication_date'))
        try:
            data, warnings = build_publication(row, metadata, claimant, faculty, students)
        except ValueError as exc:
            status = str(exc).split(':')[0]
            if status not in {'CLAIMANT_NOT_IN_DOI_AUTHORS', 'AUTHOR_IDENTITY_REVIEW', 'PUBLICATION_DATE_REVIEW'}:
                status = 'METADATA_REVIEW'
            result.update(status=status, warnings_errors=[str(exc)])
            if status == 'CLAIMANT_NOT_IN_DOI_AUTHORS':
                result['claimant_found_in_doi_authors'] = False
                result['warnings_errors'].append('DOI author names: ' + ' | '.join(a['author_name_from_source'] for a in metadata.get('authors', [])))
            return result
        result['claimant_found_in_doi_authors'] = True
        pub = save_publication(db, data)
        result.update(status='IMPORTED', publication_id=pub.id, stored_doi_title=pub.title,
                      publication_date=pub.publication_date.isoformat(), warnings_errors=warnings)
        return result
    except ImportConflict:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        result.update(status='DATABASE_ERROR', warnings_errors=[f'{type(exc).__name__}: {exc}'])
        return result


def verify_inputs(db, source, reconciliation):
    path = sqlite_database_path(db)
    assert Path(path).resolve() == LIVE.resolve(), f'Wrong import database: {path}'
    assert Path(reconciliation['database_path']).resolve() == LIVE.resolve(), 'Reconciliation database differs'
    assert source['source_sha256'] == reconciliation['source']['source_sha256'], 'Workbook differs from verified reconciliation'
    assert len(source['rows']) == 138
    faculty = list(db.scalars(select(Faculty)))
    by_employee = {f.employee_id: f for f in faculty}
    approved = {}
    for item in reconciliation['claimants']:
        for number in item['source_rows']:
            assert number not in approved
            approved[number] = item
    assert len(approved) == 138
    claimants = {}
    for row in source['rows']:
        item = approved[row['excel_row']]
        assert item['excel_author_value'] == row['Authors']
        if row['excel_row'] == 86:
            assert row['Authors'].strip() == 'Archana Chittari' and item['match_source'] == 'UNMATCHED'
            continue
        assert item['match_source'] in {'CANONICAL', 'STRONG_VARIANT'} and not item['requires_review']
        person = by_employee[item['employee_id']]
        # Validate freshness conservatively; the stored employee mapping owns import.
        check = reconcile_faculty_name(row['Authors'], faculty)
        assert check['employee_id'] == person.employee_id and not check['requires_review']
        claimants[row['excel_row']] = person
    assert len(claimants) == 137
    return faculty, list(db.scalars(select(Student))), claimants


def audit(db, results, source, backup):
    pubs = list(db.scalars(select(Publication)))
    ids = [r['publication_id'] for r in results if r['status'] == 'IMPORTED']
    imported = [p for p in pubs if p.id in ids]
    doi_groups = defaultdict(list)
    for p in pubs:
        if p.doi:
            doi_groups[historical_doi(p.doi)].append(p.id)
    assert all(len(v) == 1 for v in doi_groups.values()), 'Normalized DOI collision'
    assert len(ids) == len(set(ids)) == len(imported)
    rows = {r['excel_row']: r for r in source['rows']}
    faculty = list(db.scalars(select(Faculty)))
    by_id = {f.id: f for f in faculty}
    claims = Counter()
    indexing = Counter()
    quartiles = Counter()
    for result in results:
        if result['status'] != 'IMPORTED':
            continue
        pub = next(p for p in imported if p.id == result['publication_id'])
        claimant = [a for a in pub.authors if a.is_claiming_faculty]
        assert len(claimant) == 1
        a = claimant[0]
        assert a.is_internal and a.person_type == 'FACULTY' and a.matching_status == 'EXACT'
        assert by_id[a.faculty_id].employee_id == result['employee_id']
        metadata = pub.raw_metadata_json['message']
        assert len(pub.authors) == len(metadata.get('author') or []), 'Incomplete DOI author list'
        assert [a.author_order for a in pub.authors] == list(range(1, len(pub.authors)+1))
        for key, value in kpi_values(rows[result['excel_row']]).items():
            assert getattr(pub, key) == value, f'KPI mismatch: {key}'
        claims[result['employee_id']] += 1
        indexing.update(pub.indexing or ['NULL'])
        quartiles[pub.quartile or 'NULL'] += 1
    assert sum(claims.values()) == len(imported)
    assert sorted(r['excel_row'] for r in results) == sorted(rows), 'Rows missing or repeated'
    connection = db.connection()
    assert connection.exec_driver_sql('PRAGMA integrity_check').all() == [('ok',)]
    assert not connection.exec_driver_sql('PRAGMA foreign_key_check').all()
    # Existing data must remain byte-value equivalent in original columns.
    with sqlite3.connect(f'{Path(backup).resolve().as_uri()}?mode=ro', uri=True) as previous:
        for table in ['publications', 'publication_authors', 'faculty', 'students', 'evidence_files',
                      'change_logs', 'academic_years', 'patents', 'book_publications']:
            old = previous.execute(f'SELECT * FROM {table}').fetchall()
            columns = [r[1] for r in previous.execute(f'PRAGMA table_info({table})')]
            names = ','.join('"'+c+'"' for c in columns)
            id_pos = columns.index('id')
            for old_row in old:
                current = connection.exec_driver_sql(f'SELECT {names} FROM {table} WHERE id=?', (old_row[id_pos],)).one()
                assert tuple(current) == old_row, f'Existing {table} record changed'
        for table in ['faculty', 'students', 'evidence_files']:
            assert connection.exec_driver_sql(f'SELECT COUNT(*) FROM {table}').scalar() == previous.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    return {'integrity_check': 'ok', 'foreign_key_violations': 0, 'normalized_doi_duplicates': 0,
            'claim_uniqueness': True, 'claim_author_consistency': True, 'excel_kpis_preserved': True,
            'existing_records_preserved': True, 'row_reconciliation': dict(Counter(r['status'] for r in results)),
            'stored_historical_publications': len(imported), 'imported_unique_dois': len({p.doi for p in imported}),
            'database_publications': len(pubs), 'database_unique_dois': len(doi_groups),
            'faculty_claimed_total': sum(claims.values()),
            'claimant_summary': [{'employee_id': f.employee_id, 'faculty_name': f.name, 'imported_claimed_publications': claims[f.employee_id]} for f in faculty],
            'indexing_totals': dict(indexing), 'quartile_totals': dict(quartiles),
            'with_student_authors': sum(any(a.student_id for a in p.authors) for p in imported),
            'with_multiple_faculty_authors': sum(len({a.faculty_id for a in p.authors if a.faculty_id}) > 1 for p in imported),
            'department_kpis': department_kpis(imported)}


def write_reports(directory, report):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'import-reconciliation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['rows']:
        with (directory / 'journal-import.csv').open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(report['rows'][0]))
            writer.writeheader()
            for row in report['rows']:
                writer.writerow({k: ' | '.join(str(v) for v in val) if isinstance(val, list) else val for k, val in row.items()})
    if report.get('validation'):
        validation = report['validation']
        with (directory / 'faculty-claimed-summary.csv').open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=['employee_id', 'faculty_name', 'imported_claimed_publications'])
            writer.writeheader()
            writer.writerows(validation['claimant_summary'])
        lines = ['# Historical journal import reconciliation', '', f'Database: `{report["database_path"]}`',
                 f'Backup: `{report["backup_path"]}`', f'Source: `{report["source"]["source"]}` — Journal',
                 f'Source SHA256: `{report["source"]["source_sha256"]}`', '',
                 'All 138 rows are accounted for; 137 were eligible, with Archana Chittari excluded.', '',
                 '| Status | Rows |', '|---|---:|']
        lines.extend(f'| {status} | {count} |' for status, count in validation['row_reconciliation'].items())
        lines.extend(['', '## Remaining review rows', '', '| Excel row | Claimant | Status | Details |', '|---:|---|---|---|'])
        for row in report['rows']:
            if row['status'] != 'IMPORTED':
                detail = '; '.join(row['warnings_errors']).replace('|', ',').replace('\n', ' ')
                lines.append(f'| {row["excel_row"]} | {row["excel_claimant"]} | {row["status"]} | {detail} |')
        lines.extend(['', '## Integrity and KPI checks', '',
                      f'SQLite integrity: {validation["integrity_check"]}; foreign-key violations: 0; normalized DOI duplicates: 0.',
                      'Each imported publication has exactly one claimant who is an internal DOI author. All original records were preserved.',
                      'Excel indexing, impact factors, quartiles, and reconciled claimants match the stored imported records.',
                      f'Imported publications and unique imported DOIs: {validation["stored_historical_publications"]}.',
                      f'Sum of faculty claimed counts: {validation["faculty_claimed_total"]}.',
                      f'Total database publications and unique DOIs (includes original records): {validation["database_publications"]}.',
                      f'Indexing totals: {validation["indexing_totals"]}. Multi-index publications appear in each supported category.',
                      f'Quartile totals: {validation["quartile_totals"]}.',
                      f'With student authors: {validation["with_student_authors"]}; with multiple faculty authors: {validation["with_multiple_faculty_authors"]}.',
                      f'Excel calendar date fallback used: {sum(any("Publication date uses" in w for w in r["warnings_errors"]) for r in report["rows"])} publications; recorded in row warnings.',
                      'Unmapped DOI authors remain UNKNOWN. No faculty/student/evidence records were created.',
                      '', '## Faculty claimant summary', '', '| Employee ID | Faculty | Imported claimed publications |', '|---|---|---:|'])
        lines.extend(f'| {r["employee_id"]} | {r["faculty_name"]} | {r["imported_claimed_publications"]} |' for r in validation['claimant_summary'])
        (directory / 'import-reconciliation.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--reconciliation', required=True)
    parser.add_argument('--backup', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--retry-failed', action='store_true', help='Retry unresolved results while retaining successful rows from this run')
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    reconciliation = json.loads(Path(args.reconciliation).read_text(encoding='utf-8-sig'))
    assert hashlib.sha256(Path(source['source']).read_bytes()).hexdigest() == source['source_sha256']
    with sqlite3.connect(f'{Path(args.backup).resolve().as_uri()}?mode=ro', uri=True) as check:
        assert check.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    report = {'database_path': str(LIVE), 'backup_path': str(Path(args.backup).resolve()),
              'source': {k: v for k, v in source.items() if k != 'rows'},
              'generated_at': datetime.now(timezone.utc).isoformat(), 'eligible': 137, 'rows': []}
    previous = {}
    if args.retry_failed:
        old = json.loads((Path(args.output) / 'import-reconciliation.json').read_text(encoding='utf-8'))
        assert old['source'] == report['source'] and old['backup_path'] == report['backup_path']
        assert len(old['rows']) == 138
        previous = {r['excel_row']: r for r in old['rows']}
    metadata = CachedMetadata(Path(args.output) / 'metadata-cache')
    with SessionLocal() as db:
        faculty, students, claimants = verify_inputs(db, source, reconciliation)
        print('Verified import database: ' + sqlite_database_path(db), flush=True)
        for row in source['rows']:
            prior = previous.get(row['excel_row'])
            if prior and prior['status'] in {'IMPORTED', 'DUPLICATE', 'SKIPPED_UNRESOLVED_CLAIMANT'}:
                report['rows'].append(prior)
                continue
            result = process_row(db, row, claimants.get(row['excel_row']), faculty, students, metadata.fetch)
            if prior:
                result['warnings_errors'].extend(['Previous attempt: ' + prior['status']] if result['status'] != prior['status'] else [])
            report['rows'].append(result)
            write_reports(args.output, report)
            print(f'Excel row {row["excel_row"]}: {result["status"]}', flush=True)
        report['validation'] = audit(db, report['rows'], source, args.backup)
        write_reports(args.output, report)
        print(json.dumps(report['validation'], ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
