from conftest import paper, author, report
from test_patents import patent
from test_books import book, contributor


def test_module_dashboard_aggregates_reuse_unique_business_rules(setup):
    client, _, _ = setup
    assert client.post('/patents', json=patent()).status_code == 201
    assert client.post('/books', json=book()).status_code == 201
    p = report(client, '/patent-dashboard', '2026-07-01','2027-06-30').json()
    assert p['totals'] == report(client, '/patent-kpis','2026-07-01','2027-06-30').json()
    assert sum(m['filed'] for m in p['trend']) == 1
    assert sum(m['published'] for m in p['trend']) == 1
    assert sum(m['granted'] for m in p['trend']) == 0
    assert len(p['trend']) == 12 and p['trend'][0]['filed'] == 0
    assert p['trend'][0]['from_date'] == '2026-07-01'
    assert p['faculty'][0]['claimed'] == p['faculty'][0]['invented'] == 1
    assert p['faculty'][1]['claimed'] == 0 and p['faculty'][1]['invented'] == 1
    b = report(client, '/book-dashboard','2026-07-01','2027-06-30').json()
    assert b['totals']['total'] == b['totals']['chapters'] == 1
    assert b['totals']['international'] == 0 and b['classification_configured'] is True
    assert b['classification']['unknown'] == 1
    assert b['totals']['faculty_contributors'] == 2
    assert sum(m['chapters'] for m in b['trend']) == 1
    assert len(report(client,'/books?metric=chapters','2026-07-01','2027-06-30').json()) == b['totals']['chapters']
    assert report(client,'/book-dashboard?work_type=BOOK','2026-07-01','2027-06-30').json()['totals']['total'] == 0
    assert report(client,'/patent-dashboard?current_status=FILED','2026-07-01','2027-06-30').json()['totals']['unique'] == 0


def test_faculty_profile_correct_identity_claims_authorship_and_dates(setup):
    client, _, _ = setup
    data = paper('10.1234/profile')
    data['indexing'] = ['SCI','SCIE','SCOPUS']
    data['authors'] += [author(5,'UNKNOWN')]
    response = client.post('/publications',json=data)
    assert response.status_code == 201
    identity = response.json()['id']
    for i in range(2):
        assert client.post(f'/publications/{identity}/evidence',files={'file':(f'{i}.pdf',b'%PDF-1.4 proof','application/pdf')}).status_code == 201
    assert client.post('/patents',json=patent()).status_code == 201
    assert client.post('/books',json=book()).status_code == 201
    for faculty_id, claimed in [(1,1),(2,0)]:
        profile = report(client,f'/research/faculty/{faculty_id}','2026-07-01','2027-06-30').json()
        assert profile['faculty']['id'] == faculty_id
        assert profile['from_date'] == '2026-07-01' and profile['to_date'] == '2027-06-30'
        assert profile['summary']['journal'] == profile['summary']['publications_authored'] == 1
        assert profile['summary']['publications_claimed'] == claimed
        assert profile['summary']['patents_claimed'] == claimed and profile['summary']['patents'] == 1
        assert len(profile['publications']) == len(profile['patents']) == len(profile['books']) == 1
        assert profile['publications'][0]['claimed'] == bool(claimed)
        assert profile['summary']['consultancy'] is None
    grant = report(client,'/research/faculty/2','2027-08-12','2027-08-12').json()
    assert grant['summary']['patents'] == 1 and len(grant['patents']) == 1
    assert grant['publications'] == grant['books'] == []
    assert report(client,'/research/faculty/99999').status_code == 404


def test_editor_contribution_not_faked_as_authorship_and_partial_month(setup):
    client, _, _ = setup
    data = book('BOOK','10.1234/editor-profile','2026-08-15')
    data['contributors'] = [contributor(1,identity=1,role='EDITOR',claimant=True)]
    assert client.post('/books',json=data).status_code == 201
    result = report(client,'/book-dashboard','2026-08-15','2026-08-15').json()
    assert result['totals']['faculty_contributors'] == 1
    assert result['totals']['unique_faculty'] == 0
    assert result['faculty'][0]['authored'] == 0
    assert result['trend'][0]['from_date'] == result['trend'][0]['to_date'] == '2026-08-15'
    assert result['trend'][0]['books'] == 1
    profile = report(client,'/research/faculty/1','2026-08-15','2026-08-15').json()
    assert profile['summary']['books'] == 1
    assert len(report(client,'/books?metric=faculty_contributors','2026-08-15','2026-08-15').json()) == 1
