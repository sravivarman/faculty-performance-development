from backend.models import Faculty
from conftest import paper, author, report
from test_patents import patent, inventor
from test_books import book, contributor


def test_research_overview_distinct_records_module_reuse_and_drills(setup):
    client, factory, _ = setup
    with factory() as db:
        db.add_all([Faculty(id=3, employee_id='C', name='Faculty C'), Faculty(id=4, employee_id='D', name='Faculty D')])
        db.commit()
    for n in range(5):
        data = paper(f'10.1234/research-{n}')
        if n == 0:
            data['authors'] += [author(5, 'FACULTY', 3), author(6, 'FACULTY', 4), author(7, 'STUDENT', 2)]
        response = client.post('/publications', json=data)
        assert response.status_code == 201, response.text
        if n == 0:
            for i in range(2):
                assert client.post(f"/publications/{response.json()['id']}/evidence", files={'file': (f'{i}.pdf', b'%PDF-1.4 proof', 'application/pdf')}).status_code == 201
    assert client.post('/publications', json=paper('10.1234/outside-research', '2025-12-31')).status_code == 201
    assert client.post('/patents', json=patent()).status_code == 201
    assert client.post('/books', json=book()).status_code == 201
    response = report(client, '/research/overview', '2026-07-01', '2027-06-30')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['activity_totals']['publications'] == 5
    assert data['activity_totals']['patents'] == data['activity_totals']['books'] == 1
    assert data['patent_summary']['filed'] == data['patent_summary']['published'] == 1
    assert data['outcomes']['patents_granted'] == 0
    assert data['outcomes']['faculty_contributors'] == 4
    assert data['faculty_participation'] == {'with_activity': 4, 'without_activity': 0}
    faculty = {f['id']: f for f in data['faculty_summary']}
    assert faculty[1]['total_activities'] == 7
    assert faculty[1]['publications_claimed'] == 5 and faculty[2]['publications_claimed'] == 0
    assert faculty[2]['publications_authored'] == 5
    assert faculty[2]['journal'] == 5 and faculty[2]['conference'] == 0
    assert data['student_summary'] == {'publications': 5, 'patents': 1, 'unique_contributors': 2}
    assert sum(m['publications'] for m in data['trend']) == 5
    assert sum(m['patents'] for m in data['trend']) == 2  # same patent active in two months
    assert sum(m['books'] for m in data['trend']) == 1
    assert data['data_quality']['missing_evidence'] == 4
    assert data['data_quality']['patents_missing_evidence'] == 1
    assert len(data['recent_activity']) == 7
    pub = report(client, '/publication-dashboard', '2026-07-01', '2027-06-30').json()
    assert data['publication_summary'] == pub['totals']
    for key, path, metric in [('publications', '/publications', 'total'), ('patents', '/patents', 'unique'), ('books', '/books', 'total')]:
        records = report(client, f'{path}?metric={metric}&dashboard_only=true', '2026-07-01', '2027-06-30').json()
        assert len(records) == data['activity_totals'][key]
    for metric in ['filed', 'published', 'granted', 'missing_evidence', 'missing_lifecycle', 'with_confirmed_students']:
        assert report(client, '/patents?metric=' + metric, '2026-07-01', '2027-06-30').status_code == 200
    for identity, f in faculty.items():
        assert len(report(client, f'/research/activities?faculty_id={identity}', '2026-07-01', '2027-06-30').json()) == f['total_activities']


def test_grant_event_qualifies_once_without_new_filing(setup):
    client, _, _ = setup
    assert client.post('/patents', json=patent()).status_code == 201
    data = report(client, '/research/overview', '2027-08-12', '2027-08-12').json()
    assert data['activity_totals']['patents'] == 1
    assert data['outcomes']['patents_granted'] == 1
    assert data['outcomes']['faculty_contributors'] == 2
    assert all(f['total_activities'] == 1 and f['patents_invented'] == 1 for f in data['faculty_summary'])
    assert data['recent_activity'][0]['date'] == '2027-08-12'
    assert data['recent_activity'][0]['status'] == 'Granted'
    assert len(report(client, '/patents?metric=granted', '2027-08-12', '2027-08-12').json()) == 1


def test_missing_modules_and_empty_period_have_no_fake_finances(setup):
    client, _, _ = setup
    data = report(client, '/research/overview', '2026-07-01', '2026-07-31').json()
    assert data['activity_totals']['publications'] == data['activity_totals']['patents'] == data['activity_totals']['books'] == 0
    assert all(data['activity_totals'][key] is None for key in ['fdp', 'certifications', 'proposals', 'consultancy'])
    assert data['financial_summary'] == {'funds_sanctioned': None, 'consultancy_revenue': None}
    assert data['outcomes']['proposals_sanctioned'] is None
    assert data['faculty_participation'] == {'with_activity': 0, 'without_activity': 2}
    assert data['recent_activity'] == []


def test_unmapped_student_inventor_is_not_a_confirmed_student(setup):
    client, _, _ = setup
    data = patent()
    data['inventors'] = [inventor(1, identity=1, claim=True), inventor(2, 'STUDENT', None)]
    assert client.post('/patents', json=data).status_code == 201
    overview = report(client, '/research/overview', '2026-07-01', '2027-06-30').json()
    assert overview['student_summary']['patents'] == overview['student_summary']['unique_contributors'] == 0
    assert report(client, '/patents?metric=with_confirmed_students', '2026-07-01', '2027-06-30').json() == []


def test_whole_book_editor_is_a_participant_without_authorship(setup):
    client, _, _ = setup
    data = book('BOOK', '10.1234/editor-research')
    data['contributors'] = [contributor(1, identity=1, role='EDITOR', claimant=True)]
    assert client.post('/books', json=data).status_code == 201
    overview = report(client, '/research/overview', '2026-07-01', '2027-06-30').json()
    assert overview['outcomes']['faculty_contributors'] == 1
    row = next(f for f in overview['faculty_summary'] if f['id'] == 1)
    assert row['books'] == row['total_activities'] == 1
    assert len(report(client, '/books?metric=participated&drill_faculty_id=1').json()) == 1
    assert report(client, '/books?metric=authored&drill_faculty_id=1').json() == []


def test_preview_calendar_aggregates_zero_buckets_and_business_dates(setup):
    client, _, _ = setup
    for n, day in enumerate(['2025-12-31', '2026-01-01', '2026-03-31', '2026-04-01', '2026-06-30', '2026-07-01', '2026-12-31']):
        data = paper(f'10.1234/calendar-{n}', day)
        if n == 3:
            data['publication_type'] = 'CONFERENCE'
        assert client.post('/publications', json=data).status_code == 201
    assert client.post('/patents', json=patent()).status_code == 201
    assert client.post('/books', json=book()).status_code == 201
    monthly = report(client, '/research/overview?granularity=MONTHLY&calendar_year=2026').json()
    assert monthly['available_years'] == [2027, 2026, 2025]  # grant year is a recorded lifecycle activity year
    assert len(monthly['buckets']) == 12
    assert monthly['buckets'][1]['journal'] == 0
    assert monthly['buckets'][7]['patents'] == monthly['buckets'][7]['books'] == 1
    assert monthly['buckets'][11]['patents'] == 1  # same record active at its publication event
    quarterly = report(client, '/research/overview?granularity=QUARTERLY&calendar_year=2026').json()['buckets']
    assert [r['journal'] for r in quarterly] == [2, 1, 1, 1]
    assert [r['conference'] for r in quarterly] == [0, 1, 0, 0]
    halves = report(client, '/research/overview?granularity=HALF_YEARLY&calendar_year=2026').json()['buckets']
    assert [r['journal'] for r in halves] == [3, 2]
    annual = report(client, '/research/overview?granularity=YEARLY').json()['buckets']
    assert [r['label'] for r in annual] == ['2025', '2026', '2027']
    assert [r['journal'] for r in annual] == [1, 5, 0]
    assert annual[0]['fdp'] is None
    bounded = report(client, '/research/overview?granularity=MONTHLY&calendar_year=2026', '2026-03-31', '2026-04-01').json()['buckets']
    assert sum(r['journal'] for r in bounded) == sum(r['conference'] for r in bounded) == 1
    assert report(client, '/research/overview?granularity=WEEKLY').status_code == 422
    assert report(client, '/research/overview?granularity=MONTHLY&calendar_year=10000').status_code == 422


def test_preview_no_history_and_default_latest_year(setup):
    client, _, _ = setup
    empty = report(client, '/research/overview?granularity=MONTHLY').json()
    assert empty['available_years'] == [] and len(empty['buckets']) == 12
    assert report(client, '/research/overview?granularity=YEARLY').json()['buckets'] == []
    assert client.post('/publications', json=paper('10.1234/history', '2020-01-01')).status_code == 201
    assert report(client, '/research/overview?granularity=MONTHLY').json()['calendar_year'] == 2020
