import pytest
from sqlalchemy import select, text

from backend import book_api
from backend.doi import normalize_doi
from backend.metadata import parse_crossref, MetadataError
from backend.models import BookPublication, Publication
from conftest import report
from test_books import book, contributor


def raw(kind='book-chapter', names=('Faculty A', 'Unknown Coauthor')):
    return {'message': {'DOI': '10.1234/CHAPTER', 'type': kind, 'title': ['Fetched work'],
        'container-title': ['Parent book'], 'publisher': 'Press', 'published': {'date-parts': [[2026, 8, 15]]},
        'author': [{'name': name, 'affiliation': [{'name': 'Example affiliation'}]} for name in names],
        'editor': [{'given': 'External', 'family': 'Editor', 'ORCID': 'https://orcid.org/0000-0009-8765-4321'}],
        'ISBN': ['9780306406157'], 'isbn-type': [{'type': 'print', 'value': '9780306406157'}, {'type': 'electronic', 'value': '9783161484100'}],
        'edition-number': '2', 'volume': '3', 'page': '15–28'}}


def lookup(client, monkeypatch, source):
    monkeypatch.setattr(book_api.provider, 'fetch_by_doi', lambda doi: parse_crossref(source, doi))
    return client.get('/book-metadata?doi=https://doi.org/10.1234/CHAPTER')


@pytest.mark.parametrize('kind,expected', [('book', 'BOOK'), ('reference-book', 'BOOK'), ('edited-book', 'BOOK'),
    ('monograph', 'BOOK'), ('book-chapter', 'BOOK_CHAPTER'), ('book-section', 'BOOK_CHAPTER'),
    ('reference-entry', 'BOOK_CHAPTER'), ('book-part', 'BOOK_CHAPTER')])
def test_supported_types_mapping_and_preview_only(setup, monkeypatch, kind, expected):
    client, factory, _ = setup
    response = lookup(client, monkeypatch, raw(kind))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['work_type'] == expected and data['doi'] == '10.1234/chapter'
    assert data['title'] == 'Fetched work' and data['publisher'] == 'Press'
    assert data['edition'] == '2' and data['volume'] == '3' and data['publication_year'] == 2026
    assert data['isbn'] == '9780306406157' and data['eisbn'] == '9783161484100'
    assert data['parent_book_title'] == ('Parent book' if expected == 'BOOK_CHAPTER' else None)
    assert [c['role'] for c in data['contributors']] == ['AUTHOR', 'AUTHOR', 'EDITOR']
    assert data['contributors'][0]['faculty_id'] == 1 and data['contributors'][0]['is_claiming_faculty']
    assert data['contributors'][1]['person_type'] == 'UNKNOWN'
    with factory() as db:
        assert db.scalar(select(BookPublication)) is None and db.scalar(select(Publication)) is None


def test_source_order_matching_and_multiple_faculty_claimant_review(setup, monkeypatch):
    client, _, _ = setup
    data = lookup(client, monkeypatch, raw(names=('B. Faculty', 'Student X', 'A. Faculty', 'Unknown'))).json()
    assert [c['person_type'] for c in data['contributors']] == ['FACULTY', 'STUDENT', 'FACULTY', 'UNKNOWN', 'UNKNOWN']
    assert not any(c['is_claiming_faculty'] for c in data['contributors'])
    payload = {k:v for k,v in data.items() if k not in ('source_type', 'warnings')}
    assert client.post('/books', json=payload).status_code == 422
    payload['contributors'][2]['is_claiming_faculty'] = True
    saved = client.post('/books', json=payload)
    assert saved.status_code == 201, saved.text
    record = saved.json()
    assert record['contributors'][3]['source_metadata']['affiliation_from_source'] == ['Example affiliation']
    assert record['raw_metadata_json'] == raw(names=('B. Faculty', 'Student X', 'A. Faculty', 'Unknown'))
    assert record['metadata_source'] == 'CROSSREF' and record['metadata_fetched_at']
    assert record['edition'] == '2'
    assert report(client, '/dashboard-kpis').json()['books_total'] == 1
    overview = report(client, '/research/overview').json()
    assert overview['activity_totals']['books'] == 1
    assert [r['books'] for r in overview['faculty_summary']] == [1,1]
    assert report(client, '/book-kpis').json()['total'] == 1
    rows = report(client, '/book-kpis/faculty').json()
    assert [(r['claimed'],r['authored']) for r in rows] == [(1,1),(0,1)]
    assert len(report(client, '/research/faculty/2').json()['books']) == 1
    duplicate = client.post('/books', json=payload)
    assert duplicate.status_code == 409 and duplicate.json()['detail']['book_id'] == record['id']
    monkeypatch.setattr(book_api.provider, 'fetch_by_doi', lambda _: pytest.fail('Duplicate should not fetch'))
    assert client.get('/book-metadata?doi=doi:10.1234/CHAPTER').status_code == 409


def test_incomplete_and_ambiguous_metadata_no_invented_day(setup, monkeypatch):
    client, _, _ = setup
    source = raw('book-series', names=('Unknown author',))
    source['message']['published']['date-parts'] = [[2026]]
    for key in ('ISBN','isbn-type','page','edition-number','volume'):
        source['message'].pop(key)
    data = lookup(client, monkeypatch, source).json()
    assert 'work_type' not in data and len(data['warnings']) == 2
    assert data['publication_date'] is None and data['publication_year'] == 2026
    assert data['isbn'] is data['eisbn'] is data['volume'] is data['page_range'] is None
    assert not any(c['is_claiming_faculty'] for c in data['contributors'])
    assert client.post('/books', json={k:v for k,v in data.items() if k not in ('source_type','warnings')}).status_code == 422


@pytest.mark.parametrize('kind', ['journal-article','proceedings-article','dataset'])
def test_non_book_lookup_rejected_without_creating_publications(setup, monkeypatch, kind):
    client, factory, _ = setup
    assert lookup(client, monkeypatch, raw(kind)).status_code == 422
    with factory() as db:
        assert db.scalar(select(Publication)) is None


@pytest.mark.parametrize('doi,isbn', [('https://doi.org/10.1234/ONLY',None), (None,'9780306406157'),
    ('http://dx.doi.org/10.1234/BOTH','9780306406157'), (None,None)])
def test_manual_identifiers_independent_and_failed_lookup_nonblocking(setup, monkeypatch, doi, isbn):
    client, _, _ = setup
    def fail(_): raise MetadataError('Provider unavailable')
    monkeypatch.setattr(book_api.provider, 'fetch_by_doi', fail)
    assert client.get('/book-metadata?doi=10.1234/failure').status_code == 502
    payload = book('BOOK',doi=doi);payload['isbn'] = isbn
    payload['contributors'] = [contributor(1,identity=1,claimant=True),contributor(2,'UNKNOWN',scope='UNKNOWN')]
    response = client.post('/books',json=payload)
    assert response.status_code == 201, response.text
    assert response.json()['doi'] == normalize_doi(doi)
    assert response.json()['isbn'] == isbn


def test_new_records_need_real_active_faculty_claimant(setup):
    client, _, _ = setup
    for kind in ('STUDENT','UNKNOWN','EXTERNAL_PERSON'):
        payload = book();payload['contributors'] = [contributor(1,kind,1,scope='UNKNOWN',claimant=True)]
        assert client.post('/books',json=payload).status_code == 422
    assert client.get('/book-metadata?doi=not-a-doi').status_code == 422


def test_simultaneous_duplicate_save_returns_existing_link(setup, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    client, _, _ = setup
    payload = book()
    identity = client.post('/books', json=payload).json()['id']
    def conflict(*args):
        raise IntegrityError('INSERT', {}, Exception('unique DOI conflict'))
    monkeypatch.setattr(book_api, 'save_book', conflict)
    response = client.post('/books', json=payload)
    assert response.status_code == 409 and response.json()['detail']['book_id'] == identity


def test_additive_migration_preserves_historical_rows(tmp_path, monkeypatch):
    from backend import db as database
    from backend.db import make_engine
    from alembic import command
    from alembic.config import Config
    engine = make_engine(f'sqlite:///{tmp_path / "historical.db"}')
    monkeypatch.setattr(database, 'engine', engine)
    command.upgrade(Config('alembic.ini'), 'c931ea46d582')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO faculty (id,employee_id,name,name_variants,is_active,created_at,updated_at) VALUES (1,'OLD','Historical Faculty','[]',1,'1990-01-01','1990-01-01')"))
        conn.execute(text("INSERT INTO book_publications (id,work_type,title,publisher,publication_date,is_active,created_at,updated_at,doi) VALUES (1,'BOOK','Historical','Press','1990-01-01',1,'1990-01-01','1990-01-01',NULL)"))
        conn.execute(text("INSERT INTO book_contributors (book_record_id,contributor_order,contributor_name,role,person_type,institution_scope,faculty_id,is_claiming_faculty,created_at,updated_at) VALUES (1,1,'Historical Faculty','AUTHOR','FACULTY','CURRENT_DEPARTMENT',1,1,'1990-01-01','1990-01-01')"))
        before = dict(conn.execute(text('SELECT * FROM book_publications')).mappings().one())
        contributor_before = dict(conn.execute(text('SELECT * FROM book_contributors')).mappings().one())
    command.upgrade(Config('alembic.ini'), 'head')
    with engine.connect() as conn:
        after = dict(conn.execute(text('SELECT * FROM book_publications')).mappings().one())
        assert {key:after[key] for key in before} == before
        contributor_after = dict(conn.execute(text('SELECT * FROM book_contributors')).mappings().one())
        assert {key:contributor_after[key] for key in contributor_before} == contributor_before
        assert after['classification'] is after['metadata_source'] is after['raw_metadata_json'] is None
        assert conn.execute(text('PRAGMA foreign_key_check')).all() == []
    engine.dispose()
