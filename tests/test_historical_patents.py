import json
from datetime import date
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from backend.models import Faculty, Patent, PatentInventor
from backend.patent_schemas import PatentInput
from backend.patent_services import save_patent, patent_kpis, patent_person_kpis
from backend.dashboard_reporting import faculty_details
from backend.research_overview import overview, activity_trend
from scripts.import_historical_patents import SOURCE, IDENTITIES, reconcile, run


def seed(db):
    for employee, (name, _) in IDENTITIES.items():
        db.add(Faculty(employee_id=employee, name=name, is_active=employee!='VCE967'))
    db.add(Faculty(employee_id='VCE1546', name='G Swetha'))
    db.add(Faculty(employee_id='VCE1219', name='K Haleema'))
    db.commit()


def test_historical_import_idempotency_lifecycle_and_dashboards(setup):
    _, factory, _ = setup
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    with factory() as db:
        seed(db)
        preview = reconcile(db, source)
        assert not db.scalars(select(Patent)).all()
        assert [r['claimant_count'] for r in preview] == [5,6,1,6,4,2,3,6,1]
        unmatched = [m['source_name'] for r in preview for m in r['matching'] if m['match_source']=='CURRENT_DEPARTMENT_UNMATCHED']
        assert unmatched == ['Ms. Puligilla Swetha', 'Dr. Venkata Ramana']
        db.rollback()
        result = run(db, source, True)
        assert result['inserted']==9
        assert run(db, source, True)['existing']==9
        patents = db.scalars(select(Patent)).all()
        assert len(patents)==9
        assert len(db.scalars(select(PatentInventor)).all())==55
        assert sum(i.is_claiming_faculty for p in patents for i in p.inventors)==34
        assert sum(p.patent_type=='DESIGN' for p in patents)==2
        assert sum(p.current_status=='GRANTED' for p in patents)==1
        assert all(p.filing_date is None and not p.evidence for p in patents)
        start,end=date(2026,1,1),date(2026,12,31)
        counts=patent_kpis(patents,start,end)
        assert (counts['unique'],counts['published'],counts['granted'],counts['filed'])==(9,8,1,0)
        assert patent_kpis(patents,date(2026,5,22),date(2026,5,22))['unique']==2
        assert patent_kpis(patents,date(2025,12,16),date(2025,12,16))['published']==1
        historical=db.scalar(select(Faculty).where(Faculty.employee_id=='VCE967'))
        people=patent_person_kpis(db,patents,start,end,'faculty')
        row=next(r for r in people if r['id']==historical.id)
        assert not historical.is_active and row['invented']==row['claimed']==5
        summary=overview(db,start,end)
        assert summary['activity_totals']['patents']==9
        assert next(r for r in summary['faculty_summary'] if r['id']==historical.id)['patents_claimed']==5
        assert faculty_details(db,historical.id,start,end)['summary']['patents_claimed']==5
        trend=activity_trend(db,start,end,2026)
        assert trend['buckets'][4]['patents']==2
        assert trend['buckets'][0]['patents']==4
        # Source explicitly classifies this spelling as external on record 5,
        # even though record 6 uses the same normalized name as department.
        external=patents[4].inventors[2]
        assert external.person_type=='EXTERNAL_PERSON' and external.faculty_id is None
        assert patents[0].inventors[4].institution_scope=='CURRENT_DEPARTMENT'
        assert patents[0].inventors[4].person_type=='UNKNOWN'
        assert patents[0].application_number=='202641060300 A'
        assert patents[2].application_number=='483689-001'


def test_ambiguity_blocks_entire_import(setup):
    _,factory,_=setup
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    with factory() as db:
        seed(db)
        db.add(Faculty(employee_id='CONFLICT',name='Other',name_variants=['Nakka Srinivas']))
        db.commit()
        with pytest.raises(ValueError,match='AMBIGUOUS'):
            run(db,source,True)
        db.rollback()
        assert not db.scalars(select(Patent)).all()


def test_multiple_claims_database_constraints_and_preservation(setup):
    client,factory,_=setup
    from test_patents import patent
    data=patent(); data['inventors'][1]['is_claiming_faculty']=True
    response=client.post('/patents',json=data)
    assert response.status_code==201,response.text
    assert sum(i['is_claiming_faculty'] for i in response.json()['inventors'])==2
    with factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text('UPDATE patent_inventors SET faculty_id=1 WHERE faculty_id=2'))
        db.rollback()
    data['inventors'].append(dict(data['inventors'][0],inventor_order=4))
    assert client.post('/patents',json=data).status_code==422
