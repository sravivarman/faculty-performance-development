import copy
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select

from backend import import_journals as importer
from backend.metadata import MetadataError, parse_crossref
from backend.models import Faculty, Publication, PublicationAuthor, Student


def row(number=2, doi='https://doi.org/10.1234/import.\n'):
    return {'excel_row': number, 'S.No': number - 1, 'DoI': doi, 'Title of the paper': 'Excel title',
            'Authors': 'Faculty A', 'Name of the Journal': 'Excel journal', 'Month and Year': '2026-07-01T00:00:00',
            'Indexing': 'Scopus\nESCI', 'Impact Factor': '3.4', 'Quartile': 'Q2'}


def metadata(names=None):
    names = names or ['Faculty A', 'Faculty B', 'Student X', 'Outside Author']
    return parse_crossref({'message': {'DOI': '10.1234/import', 'type': 'journal-article',
                        'title': ['DOI title'], 'container-title': ['DOI journal'],
                        'published': {'date-parts': [[2026, 8, 19]]},
                        'author': [{'name': n, 'affiliation': [{'name': 'Institution'}]} for n in names]}}, '10.1234/import')


@pytest.mark.parametrize('value', ['10.1234/import', ' https://doi.org/10.1234/IMPORT.\n',
                                 'http://dx.doi.org/10.1234/import', 'doi:10.1234/import',
                                 'https://doi.org/10.1234/import\nPDF',
                                 'https://doi.org/10.1234/importDigitalObjectIdentifier(DOI)',
                                 'DOI:https://doi.org/10.1234/import'])
def test_doi_forms(value):
    assert importer.historical_doi(value) == '10.1234/import'


@pytest.mark.parametrize('key,value,status', [('Indexing','Index X','INDEXING_REVIEW'),
                                            ('Impact Factor','nan','INVALID_IMPACT_FACTOR'),
                                            ('Impact Factor',-1,'INVALID_IMPACT_FACTOR'),
                                            ('Quartile','Q5','INVALID_QUARTILE')])
def test_invalid_kpis(key, value, status):
    source = row(); source[key] = value
    with pytest.raises(ValueError, match=status):
        importer.kpi_values(source)


def test_blank_kpis_are_null():
    source = row(); source.update({'Impact Factor': '', 'Quartile': '', 'Indexing': ''})
    assert importer.kpi_values(source) == {'impact_factor': None, 'quartile': None, 'indexing': []}


def people(db):
    return list(db.scalars(select(Faculty))), list(db.scalars(select(Student)))


def test_import_complete_authors_claim_kpis_duplicate_idempotence(setup):
    _, factory, _ = setup
    with factory() as db:
        faculty, students = people(db)
        result = importer.process_row(db, row(), faculty[0], faculty, students, lambda _: metadata())
        assert result['status'] == 'IMPORTED'
        pub = db.get(Publication, result['publication_id'])
        assert pub.title == 'DOI title' and pub.publication_date == date(2026,8,19)
        assert pub.indexing == ['SCOPUS','ESCI'] and pub.impact_factor == 3.4 and pub.quartile == 'Q2'
        assert len(pub.authors) == 4
        assert [a.author_order for a in pub.authors] == [1,2,3,4]
        assert [a.person_type for a in pub.authors] == ['FACULTY','FACULTY','STUDENT','UNKNOWN']
        assert [a.is_claiming_faculty for a in pub.authors] == [True,False,False,False]
        def forbidden(_):
            pytest.fail('Duplicate DOI must be checked before metadata fetch')
        again = importer.process_row(db, row(), faculty[1], faculty, students, forbidden)
        assert again['status'] == 'DUPLICATE' and again['publication_id'] == pub.id
        assert db.scalar(select(func.count()).select_from(Publication)) == 1
        assert pub.authors[0].faculty_id == faculty[0].id


def test_skip_archana_before_fetch_or_master_creation(setup):
    _, factory, _ = setup
    with factory() as db:
        faculty, students = people(db)
        source = row(86); source['Authors'] = 'Archana Chittari'
        result = importer.process_row(db, source, None, faculty, students, lambda _: pytest.fail('No fetch'))
        assert result['status'] == 'SKIPPED_UNRESOLVED_CLAIMANT'
        assert db.scalar(select(func.count()).select_from(Publication)) == 0
        assert len(people(db)[0]) == 2


@pytest.mark.parametrize('name', ['Faculty Z', 'Facult A', 'Weak Alias'])
def test_claimant_must_be_conservative_author_match(setup, name):
    _, factory, _ = setup
    with factory() as db:
        faculty, students = people(db)
        faculty[0].name_variants = ['Weak Alias']
        faculty[0].name_variant_strengths = {'weak alias': 'WEAK'}
        result = importer.process_row(db, row(), faculty[0], faculty, students, lambda _: metadata([name]))
        assert result['status'] == 'CLAIMANT_NOT_IN_DOI_AUTHORS'
        assert db.scalar(select(func.count()).select_from(Publication)) == 0


def test_strong_variant_and_excel_date_fallback(setup):
    _, factory, _ = setup
    with factory() as db:
        faculty, students = people(db)
        data = metadata(['A. Faculty']); data.update(title='', journal_conference_name=None, publication_date=None)
        result = importer.process_row(db, row(), faculty[0], faculty, students, lambda _: data)
        assert result['status'] == 'IMPORTED' and result['warnings_errors']
        pub = db.get(Publication,result['publication_id'])
        assert pub.title == 'Excel title' and pub.journal_conference_name == 'Excel journal'
        assert pub.publication_date == date(2026,7,1)


def test_row_rollback_does_not_prevent_next_row(setup, monkeypatch):
    _, factory, _ = setup
    original = importer.save_publication
    with factory() as db:
        faculty, students = people(db)
        def fail(session, data):
            pub = Publication(**data.model_dump(exclude={'authors','duplicate_acknowledged'}))
            session.add(pub); session.flush()
            raise RuntimeError('Injected flush failure')
        # Database failures are contained per row; actual conflict guards stop.
        def db_failure(session, data):
            fail(session,data)
        def injected(session, data):
            try: db_failure(session, data)
            except RuntimeError: raise ValueError('Injected database failure')
        monkeypatch.setattr(importer,'save_publication',injected)
        result = importer.process_row(db,row(),faculty[0],faculty,students,lambda _:metadata())
        assert result['status'] == 'DATABASE_ERROR'
        assert db.scalar(select(func.count()).select_from(Publication)) == 0
        monkeypatch.setattr(importer,'save_publication',original)
        assert importer.process_row(db,row(),faculty[0],faculty,students,lambda _:metadata())['status'] == 'IMPORTED'


def test_retry_429_and_cache_without_second_request(tmp_path):
    class Provider:
        calls = 0
        def fetch_by_doi(self, doi):
            self.calls += 1
            if self.calls == 1:
                response = httpx.Response(429, headers={'Retry-After':'3'}, request=httpx.Request('GET','https://api.crossref.org'))
                try: response.raise_for_status()
                except httpx.HTTPStatusError as cause: raise MetadataError('temporary') from cause
            return metadata()
    provider = Provider(); delays = []
    cache = importer.CachedMetadata(tmp_path,provider,delays.append)
    cache.fetch('10.1234/import'); cache.fetch('10.1234/import')
    assert provider.calls == 2 and delays == [3]
    importer.CachedMetadata(tmp_path,provider,delays.append).fetch('10.1234/import')
    assert provider.calls == 2


def test_missing_doi_reports_invalid_without_fetch(setup):
    _, factory, _ = setup
    with factory() as db:
        faculty, students = people(db)
        assert importer.process_row(db,row(47,None),faculty[0],faculty,students,lambda _:pytest.fail('No fetch'))['status'] == 'INVALID_DOI'


def test_edit_omitting_impact_factor_preserves_imported_value(setup):
    from backend.schemas import PublicationInput
    from backend.services import save_publication
    _, factory, _ = setup
    with factory() as db:
        faculty, students = people(db)
        result = importer.process_row(db,row(),faculty[0],faculty,students,lambda _:metadata())
        pub = db.get(Publication,result['publication_id'])
        payload = metadata(); payload.update(indexing=['SCI'], quartile='Q1')
        payload, _ = importer.build_publication(row(),payload,faculty[0],faculty,students)
        values = payload.model_dump(); values.pop('impact_factor')
        save_publication(db,PublicationInput(**values),pub)
        assert pub.impact_factor == 3.4
        values['impact_factor'] = None
        save_publication(db,PublicationInput(**values),pub)
        assert pub.impact_factor is None
