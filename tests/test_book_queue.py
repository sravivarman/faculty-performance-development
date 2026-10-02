import pytest
from backend import book_api
from backend.doi import parse_doi_input
from backend.metadata import MetadataError, parse_crossref
from test_book_doi import raw
from test_books import book, contributor
from conftest import report


@pytest.mark.parametrize('content', ['10.1234/a\n10.1234/b', '10.1234/a,10.1234/b',
    '10.1234/a;10.1234/b', '10.1234/a https://doi.org/10.1234/b', 'doi: 10.1234/a DOI: 10.1234/B'])
def test_shared_parser_spaces_and_separators(content):
    assert [r['doi'] for r in parse_doi_input(content)] == ['10.1234/a','10.1234/b']


def validate(client, draft, resolved=True):
    response = client.post('/book-preview-validation', json={'draft':draft,'type_resolved':resolved})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('kinds', [('book-chapter','book-chapter'), ('book','book'), ('book','book-chapter')])
def test_mixed_or_uniform_batch_independent_lookup_validation_save_and_counts(setup, monkeypatch, kinds):
    client, _, _ = setup
    calls=[]
    def provider(doi):
        calls.append(doi)
        if doi.endswith('failed'): raise MetadataError('Unavailable')
        source=raw(kinds[int(doi[-1])], names=('Faculty A','Faculty B','Unknown Coauthor'))
        source['message']['DOI']=doi
        return parse_crossref(source,doi)
    monkeypatch.setattr(book_api.provider,'fetch_by_doi',provider)
    entries=client.post('/publications/parse-dois',json={'content':'10.1234/item0\nhttps://doi.org/10.1234/ITEM0;bad;10.1234/failed;10.1234/item1'}).json()['entries']
    assert len(entries)==4 and entries[1]['status']=='INVALID_DOI'
    ready=[]
    for item in entries:
        if not item['doi']: continue
        response=client.get('/book-metadata',params={'doi':item['doi']})
        if item['doi'].endswith('failed'):
            assert response.status_code==502;continue
        draft=response.json()
        assert validate(client,draft)['status']=='NEEDS_CLAIMANT'
        draft['contributors'][0]['is_claiming_faculty']=True
        assert validate(client,draft)['status']=='READY'
        ready.append(draft)
    assert calls==['10.1234/item0','10.1234/failed','10.1234/item1']
    assert client.get('/books').json()==[]  # Validation and fetching never persist.
    for draft in ready:
        assert client.post('/books',json=draft).status_code==201
        assert validate(client,draft)['status']=='DUPLICATE'
        assert client.post('/books',json=draft).status_code==409
    counts=report(client,'/book-kpis').json()
    assert counts['total']==2 and counts['books']==kinds.count('book') and counts['chapters']==kinds.count('book-chapter')
    faculty=report(client,'/book-kpis/faculty').json()
    assert [(r['claimed'],r['authored']) for r in faculty]==[(2,2),(0,2)]
    assert report(client,'/research/overview').json()['activity_totals']['books']==2
    assert len(report(client,'/research/faculty/2').json()['books'])==2


def test_unknown_nonblocking_but_book_editor_cannot_claim_in_doi_queue(setup):
    client, _, _=setup
    draft=book('BOOK');draft['contributors']=[contributor(1,identity=1,claimant=True),contributor(2,'UNKNOWN',scope='UNKNOWN')]
    assert validate(client,draft)['status']=='READY'
    draft['contributors'][0]['role']='EDITOR'
    assert validate(client,draft)['status']=='NEEDS_REVIEW'


def test_validation_reports_type_fields_claimant_and_real_master_errors(setup):
    client, _, _=setup
    draft=book()
    assert validate(client,draft,False)['status']=='NEEDS_REVIEW'
    draft['contributors'][0]['is_claiming_faculty']=False
    assert validate(client,draft)['status']=='NEEDS_CLAIMANT'
    draft['contributors'][0]['faculty_id']=999
    assert validate(client,draft)['status']=='NEEDS_REVIEW'
    for key,value in [('page_range',None),('publisher',''),('publication_date','2026-02-30'),('isbn','bad')]:
        data=book();data[key]=value
        assert validate(client,data)['status']=='NEEDS_REVIEW'
    for value in [None,'not a DOI']:
        data=book();data['doi']=value
        assert validate(client,data)['status']=='INVALID_DOI'
    assert client.post('/book-preview-validation',json={'draft':[]}).status_code==422


def test_partial_save_keeps_duplicate_and_failed_items_without_affecting_ready_records(setup, monkeypatch):
    client, _, _=setup
    existing=client.post('/books',json=book(doi='10.1234/existing')).json()
    duplicate=validate(client,book(doi='https://doi.org/10.1234/EXISTING'))
    assert duplicate['status']=='DUPLICATE'
    assert duplicate['existing']['id']==existing['id'] and duplicate['existing']['contributors'][0]['is_claiming_faculty']
    monkeypatch.setattr(book_api.provider,'fetch_by_doi',lambda doi: (_ for _ in ()).throw(MetadataError('Failure')))
    assert client.get('/book-metadata',params={'doi':'10.1234/failed'}).status_code==502
    invalid=book(doi='wrong');ready=book(doi='10.1234/ready')
    assert validate(client,invalid)['status']=='INVALID_DOI'
    assert validate(client,ready)['status']=='READY'
    assert client.post('/books',json=ready).status_code==201
    assert len(client.get('/books').json())==2
