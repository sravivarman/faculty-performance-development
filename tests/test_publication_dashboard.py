from conftest import paper, author, report
from backend.models import Faculty


def test_distinct_dashboard_and_drills(setup):
    client, factory, _ = setup
    with factory() as db:
        db.add(Faculty(id=3, employee_id='C', name='Faculty C'))
        db.commit()
    for i in range(5):
        data = paper(f'10.1234/dashboard-{i}')
        data['publication_type'] = 'JOURNAL' if i < 3 else 'CONFERENCE'
        data['conference_name'] = 'Research Conference' if i >= 3 else None
        data['classification'] = 'INTERNATIONAL' if i < 3 else 'NATIONAL'
        data['quartile'] = 'Q1' if i == 0 else 'UNKNOWN'
        data['indexing'] = ['SCIE', 'SCOPUS', 'WEB_OF_SCIENCE'] if i == 0 else ['UNKNOWN']
        if i == 0:
            data['authors'].append(author(5, 'STUDENT', 2))
            data['authors'].append({**author(6, 'UNKNOWN'), 'affiliation_from_source': ['Vardhaman College of Engineering']})
            data['authors'].append(author(7, 'FACULTY', 3))
        result = client.post('/publications', json=data)
        assert result.status_code == 201, result.text
        if i == 0:
            for n in range(2):
                response = client.post(f"/publications/{result.json()['id']}/evidence", files={'file': (f'{n}.pdf', b'%PDF-1.4 test', 'application/pdf')})
                assert response.status_code in (200, 201), response.text
    outside = paper('10.1234/outside', '2025-12-31')
    assert client.post('/publications', json=outside).status_code == 201
    response = report(client, '/publication-dashboard', '2026-09-01', '2026-09-30')
    assert response.status_code == 200, response.text
    data = response.json()
    totals = data['totals']
    assert totals['total'] == 5 and totals['journal'] == 3 and totals['conference'] == 2
    assert totals['scie'] == totals['scopus'] == totals['q1'] == 1
    assert totals['indexed'] == 1
    assert totals['faculty_claimants'] == 1
    assert totals['with_students'] == 5 and totals['unique_students'] == 2
    assert totals['unclassified_internal_authors'] == 1
    assert totals['missing_evidence'] == 4
    faculty = {f['id']: f for f in data['faculty']}
    assert faculty[1]['claimed'] == 5 and faculty[2]['claimed'] == 0
    assert faculty[1]['authored'] == faculty[2]['authored'] == 5
    assert faculty[2]['q1'] == 1 and faculty[2]['sci_scie'] == 1
    assert faculty[3]['authored'] == 1 and faculty[3]['claimed'] == 0
    assert data['trend'] == [{'month': '2026-09', 'total': 5, 'journal': 3, 'conference': 2, 'from_date':'2026-09-01', 'to_date':'2026-09-30'}]
    assert len(data['recent']) == 5
    for metric in ['total', 'journal', 'conference', 'indexed', 'scie', 'scopus', 'q1', 'with_students', 'indexing_unknown', 'classification_unknown', 'quartile_unknown', 'missing_evidence', 'internal_unknown']:
        drill = report(client, f'/publications?dashboard_only=true&metric={metric}', '2026-09-01', '2026-09-30')
        assert drill.status_code == 200, drill.text
        assert len(drill.json()) == totals[metric], metric
    for identity, row in faculty.items():
        for metric in ['claimed', 'authored', 'journal_claimed', 'conference_claimed', 'scopus', 'sci_scie', 'q1', 'q2', 'with_students']:
            drill = report(client, f'/publications?dashboard_only=true&drill_faculty_id={identity}&metric={metric}', '2026-09-01', '2026-09-30')
            assert len(drill.json()) == row[metric], (identity, metric)


def test_dashboard_filters_and_inclusive_bounds(setup):
    client, _, _ = setup
    for day in ['2026-09-01', '2026-09-30', '2026-10-01']:
        data = paper(f'10.1234/{day}', day)
        data['quartile'] = 'NOT_APPLICABLE'
        data['classification'] = 'OTHER'
        data['indexing'] = ['OTHER']
        assert client.post('/publications', json=data).status_code == 201
    filters = 'publication_type=JOURNAL&faculty_id=2&indexing=OTHER&quartile=NOT_APPLICABLE&classification=OTHER'
    data = report(client, '/publication-dashboard?' + filters, '2026-09-01', '2026-09-30').json()
    assert data['totals']['total'] == data['totals']['indexing_other'] == data['totals']['other'] == data['totals']['not_applicable'] == 2
    assert len(report(client, '/publications?dashboard_only=true&metric=total&' + filters, '2026-09-01', '2026-09-30').json()) == 2
    assert report(client, '/publication-dashboard?publication_type=CONFERENCE', '2026-09-01', '2026-09-30').json()['totals']['total'] == 0


def test_one_publication_with_two_students_and_month_gaps(setup):
    client, _, _ = setup
    data = paper('10.1234/two-students')
    data['authors'].append(author(5, 'STUDENT', 2))
    data['quartile'] = None
    data['indexing'] = []
    assert client.post('/publications', json=data).status_code == 201
    dashboard = report(client, '/publication-dashboard', '2026-07-01', '2026-10-31').json()
    assert dashboard['totals']['total'] == dashboard['totals']['with_students'] == 1
    assert dashboard['totals']['unique_students'] == 2
    assert dashboard['totals']['indexing_unknown'] == dashboard['totals']['quartile_unknown'] == 1
    assert [m['total'] for m in dashboard['trend']] == [0, 0, 1, 0]
    for key in ['indexing_unknown', 'quartile_unknown']:
        assert len(report(client, '/publications?metric=' + key).json()) == 1
