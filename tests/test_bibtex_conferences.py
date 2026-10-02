import copy
from datetime import date

import pytest
from sqlalchemy import func, select

from backend import main
from backend.metadata import MetadataError
from backend.models import Publication
from conftest import author, paper, report


ARTICLE = r'''@article{test2026,
  author = {Asif, Md and Karuppiah, N},
  title = {Example Energy Paper}, journal = {Energy and Buildings},
  year = {2026}, volume = {350}, pages = {117359}, doi = {https://doi.org/10.1234/EXAMPLE}
}'''
CONFERENCE = r'''@inproceedings{testconf2026,
  author = {Ravivarman, S and Kumar, A}, title = {AI Based Energy Management},
  booktitle = {2026 International Conference on Smart Energy Systems},
  year = {2026}, pages = {101--106}, publisher = {IEEE}, doi = {10.1234/conference-example}
}'''
INTERNAL = '''@conference{internal, author={A, Faculty and B, Faculty and X, Student and Outside, Person},
 title={Conference collaboration},booktitle={Smart Energy Proceedings},eventtitle={Smart Energy 2026},
 year={2026},date={2026-09-18},address={Chennai},organization={Energy Society},isbn={978-1-2345-6789-0}}
'''


def parse(client, content, enrich=False):
    response = client.post('/publications/parse-bibtex',json={'content':content,'enrich_doi':enrich})
    assert response.status_code == 200, response.text
    return response.json()['entries']


def test_requested_journal_and_conference_examples(setup):
    client, factory, _ = setup
    entries = parse(client, ARTICLE+'\n'+CONFERENCE)
    assert len(entries) == 2
    a, b = [e['publication'] for e in entries]
    assert a['publication_type'] == 'JOURNAL'
    assert a['doi'] == '10.1234/example' and a['volume'] == '350'
    assert a['journal_conference_name'] == 'Energy and Buildings'
    assert [p['author_name_from_source'] for p in a['authors']] == ['Md Asif','N Karuppiah']
    assert entries[0]['publication_year'] == '2026' and entries[0]['status'] == 'MISSING_DATE'
    assert b['publication_type'] == 'CONFERENCE'
    assert b['proceedings_title'] == '2026 International Conference on Smart Energy Systems'
    assert b['publisher'] == 'IEEE' and b['pages_or_article_number'] == '101--106'
    assert b['doi'] == '10.1234/conference-example'
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Publication)) == 0


def test_bad_entry_does_not_lose_neighbors(setup):
    client, _, _ = setup
    bad = '\n@article{broken, author={Broken Author\n'
    entries = parse(client,ARTICLE+bad+CONFERENCE+'\n'+INTERNAL)
    assert len(entries) == 4
    assert entries[1]['status'] == 'PARSE_ERROR'
    assert 'braces' in entries[1]['errors'][0]
    assert entries[0]['publication']['title'] == 'Example Energy Paper'
    assert entries[2]['publication']['publication_type'] == 'CONFERENCE'
    assert entries[3]['publication']['title'] == 'Conference collaboration'


def test_quotes_braces_latex_macros_suffix_corporate_names(setup):
    client, _, _ = setup
    content = r'''@string{venue="Energy Journal"}
@article{special, author={Garc\'ia, Jr, Jos\'e and {Research and Development Group}},
 title="A {nested} title with \& energy",journal=venue,month=jan,year={2026}}'''
    entry = parse(client,content)[0]
    draft = entry['publication']
    assert draft['title'] == 'A nested title with & energy'
    assert draft['journal_conference_name'] == 'Energy Journal'
    assert len(draft['authors']) == 2
    assert draft['authors'][0]['author_name_from_source'] == 'José García Jr'
    assert draft['authors'][1]['author_name_from_source'] == 'Research and Development Group'
    assert draft['raw_bibtex'].startswith('@article{special')
    assert draft['publication_date'] is None


def test_conference_no_doi_claimant_students_evidence_and_edit(setup):
    client, _, _ = setup
    draft = parse(client,INTERNAL)[0]['publication']
    assert [a['person_type'] for a in draft['authors']] == ['FACULTY','FACULTY','STUDENT','UNKNOWN']
    assert not any(a['is_claiming_faculty'] for a in draft['authors'])
    assert client.post('/publications',json=draft).status_code == 422
    draft['authors'][1]['is_claiming_faculty'] = True
    draft.update(indexing=['SCOPUS','WEB_OF_SCIENCE'],impact_factor=0.5,quartile='Q2',
                 conference_start_date='2026-09-15',conference_end_date='2026-09-17')
    response = client.post('/publications',json=draft)
    assert response.status_code == 201,response.text
    pub = response.json()
    assert pub['doi'] is None and pub['source_type'] == 'BIBTEX' and pub['raw_bibtex'].strip() == INTERNAL.strip()
    assert pub['conference_name'] == 'Smart Energy 2026' and pub['conference_location'] == 'Chennai'
    assert pub['impact_factor'] == 0.5 and pub['internal_faculty_count'] == 2
    counts = report(client,'/publication-kpis').json()
    assert counts['total'] == counts['conference'] == counts['with_students'] == 1
    rows = report(client,'/publication-kpis/faculty').json()
    assert rows[0]['conference_authored'] == 1 and rows[0]['conference_claimed'] == 0
    assert rows[1]['conference_authored'] == rows[1]['conference_claimed'] == 1
    assert sum(r['claimed'] for r in rows) == 1
    evidence = client.post(f'/publications/{pub["id"]}/evidence',files={'file':('certificate.pdf',b'%PDF-1.4 certificate','application/pdf')},data={'evidence_type':'CERTIFICATE'})
    assert evidence.status_code == 201
    draft['title'] = 'Edited conference';draft['impact_factor'] = None
    edited = client.put(f'/publications/{pub["id"]}',json=draft)
    assert edited.status_code == 200 and edited.json()['impact_factor'] is None
    assert edited.json()['evidence_count'] == 1


def test_doi_enrichment_keeps_bibtex_values_exposes_differences(setup, monkeypatch):
    client, _, _ = setup
    class Provider:
        def fetch_by_doi(self,doi):
            return dict(paper(doi),title='DOI title',publisher='DOI publisher',metadata_source='CROSSREF',
                        metadata_fetched_at='2026-10-02T00:00:00Z',raw_metadata_json={'message':{'DOI':doi}})
    monkeypatch.setattr(main,'provider',Provider())
    draft = parse(client,ARTICLE,enrich=True)[0]
    pub = draft['publication']
    assert pub['title'] == 'Example Energy Paper' and pub['publisher'] == 'DOI publisher'
    assert pub['publication_date'] == '2026-09-18'
    assert pub['indexing'] == [] and pub['quartile'] is None and pub['impact_factor'] is None
    assert pub['source_type'] == 'BIBTEX_PLUS_DOI'
    assert any(d['field'] == 'title' and d['doi'] == 'DOI title' for d in draft['differences'])
    assert len(pub['authors']) == 2 and not any(a['is_claiming_faculty'] for a in pub['authors'])


def test_provider_failure_keeps_editable_preview(setup, monkeypatch):
    client, _, _ = setup
    class Provider:
        def fetch_by_doi(self,doi): raise MetadataError('Provider unavailable')
    monkeypatch.setattr(main,'provider',Provider())
    entry = parse(client,ARTICLE,enrich=True)[0]
    assert entry['publication']['source_type'] == 'BIBTEX'
    assert 'Provider unavailable' in entry['warnings'][0]


def test_doi_duplicate_checked_before_fetch_and_within_paste(setup, monkeypatch):
    client, _, _ = setup
    saved = client.post('/publications',json=paper('10.1234/example')).json()
    class Provider:
        def fetch_by_doi(self,doi): pytest.fail('Existing DOI should not fetch metadata')
    monkeypatch.setattr(main,'provider',Provider())
    entries = parse(client,ARTICLE+'\n'+ARTICLE.replace('test2026','another'),enrich=True)
    assert all(e['status'] == 'DUPLICATE' for e in entries)
    assert entries[0]['duplicate_ids'] == [saved['id']] and entries[1]['duplicate_entry'] == 1


def test_no_doi_duplicate_warning_acknowledged_not_merged(setup):
    client, _, _ = setup
    draft = parse(client,INTERNAL)[0]['publication'];draft['authors'][0]['is_claiming_faculty'] = True
    assert client.post('/publications',json=draft).status_code == 201
    assert parse(client,INTERNAL)[0]['status'] == 'DUPLICATE'
    duplicate = client.post('/publications',json=draft)
    assert duplicate.status_code == 409 and duplicate.json()['detail']['possible_duplicate_ids']
    draft['duplicate_acknowledged'] = True
    assert client.post('/publications',json=draft).status_code == 201


def test_unknown_type_requires_classification_and_dates_validated(setup):
    client, _, _ = setup
    entry = parse(client,INTERNAL.replace('@conference','@unpublished'))[0]
    assert entry['status'] == 'AUTHOR_REVIEW' and entry['warnings']
    draft = entry['publication'];draft['authors'][0]['is_claiming_faculty'] = True
    assert client.post('/publications',json=draft).status_code == 422
    draft.update(publication_type='CONFERENCE',conference_start_date='2026-09-20',conference_end_date='2026-09-19')
    assert client.post('/publications',json=draft).status_code == 422


def test_type_kpi_range_claimant_quartile_and_drilldown(setup):
    client, _, _ = setup
    for i in range(5):
        payload=paper(f'10.1234/type-{i}');payload.update(publication_type='JOURNAL' if i<3 else 'CONFERENCE',quartile='Q1' if i<3 else 'Q2')
        payload['authors'][0]['is_claiming_faculty']=False;payload['authors'][1]['is_claiming_faculty']=True
        assert client.post('/publications',json=payload).status_code == 201
    k=report(client,'/publication-kpis').json()
    assert (k['total'],k['journal'],k['conference'],k['q1'],k['q2']) == (5,3,2,3,2)
    assert len(client.get('/publications?metric=conference_claimed&drill_faculty_id=2').json()) == 2
    assert client.get('/publications?metric=conference_claimed&drill_faculty_id=1').json() == []
    assert len(client.get('/publications?metric=journal_authored&drill_faculty_id=1').json()) == 3
    assert len(client.get('/publications?claiming_faculty_id=2&quartile=Q2').json()) == 2
    assert report(client,'/publication-kpis',from_date='2026-10-01',to_date='2026-10-31').json()['total'] == 0
    overview=report(client,'/dashboard-kpis').json()
    assert overview['publications_journal'] == 3 and overview['publications_conference'] == 2


def test_inactive_claimant_cannot_be_added_but_historical_claim_preserved(setup):
    from backend.models import Faculty
    client,factory,_=setup
    existing=client.post('/publications',json=paper()).json()
    with factory() as db:
        db.get(Faculty,1).is_active=False;db.commit()
    assert client.post('/publications',json=paper('10.1234/new-inactive')).status_code == 422
    assert client.put(f'/publications/{existing["id"]}',json=paper()).status_code == 200


def test_crossref_conference_event_fields_use_existing_parser():
    from backend.metadata import parse_crossref
    parsed=parse_crossref({'message':{'DOI':'10.1234/event','type':'proceedings-article','title':['Conference paper'],
                          'container-title':['Energy Proceedings'],'event':{'name':'Energy Conference','location':'Chennai',
                          'start':{'date-parts':[[2026,9,15]]},'end':{'date-parts':[[2026,9,17]]}},
                          'published':{'date-parts':[[2026,9,20]]}}},'10.1234/event')
    assert parsed['publication_type']=='CONFERENCE' and parsed['proceedings_title']=='Energy Proceedings'
    assert parsed['conference_name']=='Energy Conference' and parsed['conference_location']=='Chennai'
    assert parsed['conference_start_date']=='2026-09-15' and parsed['conference_end_date']=='2026-09-17'


def test_new_unknown_type_is_rejected_without_affecting_existing_records(setup):
    client,_,_=setup
    draft=paper();draft['publication_type']='OTHER'
    assert client.post('/publications',json=draft).status_code==422
    assert client.get('/publications').json()==[]
