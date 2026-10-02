import csv
import io
import json
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend import db as database
from backend.models import Faculty
from scripts.import_historical_patents import SOURCE, IDENTITIES, run
from test_patents import patent


@pytest.mark.parametrize('kind',['UTILITY','DESIGN','COPYRIGHT'])
def test_create_edit_and_validate_patent_type(setup,kind):
    client,_,_=setup
    payload=patent(kind);payload['patent_type']=kind
    result=client.post('/patents',json=payload)
    assert result.status_code==201,result.text
    assert result.json()['patent_type']==kind
    payload['title']='Edited '+kind
    assert client.put('/patents/'+str(result.json()['id']),json=payload).json()['patent_type']==kind


@pytest.mark.parametrize('kind',['OTHER','INVALID','Utility',None,''])
def test_reject_unsupported_types(setup,kind):
    client,_,_=setup
    payload=patent();payload['patent_type']=kind
    assert client.post('/patents',json=payload).status_code==422
    assert client.get('/patents',params={'patent_type':kind or 'OTHER'}).status_code==422


def test_filters_type_breakdowns_faculty_modal_and_exports(setup):
    client,factory,_=setup
    for kind in ['UTILITY','DESIGN','COPYRIGHT']:
        payload=patent(kind);payload.update(patent_type=kind,filing_date=None,grant_date=None,current_status='PUBLISHED',publication_date='2026-06-01')
        assert client.post('/patents',json=payload).status_code==201
    query='from_date=2026-01-01&to_date=2026-12-31'
    assert client.get('/patent-dashboard?'+query).json()['types']=={'UTILITY':1,'DESIGN':1,'COPYRIGHT':1}
    assert client.get('/research/overview?'+query).json()['patent_types']=={'UTILITY':1,'DESIGN':1,'COPYRIGHT':1}
    for kind in ['UTILITY','DESIGN','COPYRIGHT']:
        filtered=client.get('/patents?'+query+'&patent_type='+kind).json()
        assert len(filtered)==1 and filtered[0]['patent_type']==kind
        dashboard=client.get('/patent-dashboard?'+query+'&patent_type='+kind).json()
        assert dashboard['totals']['unique']==1
        assert dashboard['types']=={t:int(t==kind) for t in ['UTILITY','DESIGN','COPYRIGHT']}
        export=client.get('/patent-export?'+query+'&patent_type='+kind)
        assert export.status_code==200 and 'attachment' in export.headers['content-disposition']
        rows=list(csv.DictReader(io.StringIO(export.content.decode('utf-8-sig'))))
        assert len(rows)==1 and rows[0]['patent_type']==kind and rows[0]['patent_type_label']==kind.title()
    profile=client.get('/research/faculty/1?'+query).json()
    assert {p['patent_type'] for p in profile['patents']}=={'UTILITY','DESIGN','COPYRIGHT'}
    assert client.get('/patent-dashboard?from_date=2027-01-01&to_date=2027-12-31').json()['types']=={'UTILITY':0,'DESIGN':0,'COPYRIGHT':0}
    with factory() as db:
        for sql in ["UPDATE patents SET patent_type='OTHER'", "UPDATE patents SET current_status='INVALID'"]:
            with pytest.raises(IntegrityError):
                db.execute(text(sql))
            db.rollback()


def test_type_migration_preserves_records_and_all_claims(setup,monkeypatch):
    client,factory,_=setup
    for kind in ['UTILITY','DESIGN']:
        payload=patent(kind);payload['patent_type']=kind;payload['inventors'][1]['is_claiming_faculty']=True
        assert client.post('/patents',json=payload).status_code==201
    with factory() as db:
        engine=db.get_bind()
        snapshot={table:db.execute(text('SELECT * FROM '+table+' ORDER BY id')).all() for table in ['patents','patent_inventors','patent_status_history','patent_change_logs']}
    monkeypatch.setattr(database,'engine',engine)
    command.downgrade(Config('alembic.ini'),'a03d26e71001')
    command.upgrade(Config('alembic.ini'),'head')
    with factory() as db:
        for table,rows in snapshot.items():
            assert db.execute(text('SELECT * FROM '+table+' ORDER BY id')).all()==rows
        assert not db.execute(text('PRAGMA foreign_key_check')).all()


def test_historical_types_unchanged_and_future_copyright_import_supported(setup):
    _,factory,_=setup
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    with factory() as db:
        for employee,(name,_) in IDENTITIES.items():db.add(Faculty(employee_id=employee,name=name))
        db.commit()
        imported=run(db,source,True)
        assert [r['type'] for r in imported['records']].count('UTILITY')==7
        assert [r['type'] for r in imported['records']].count('DESIGN')==2
        before=db.execute(text('SELECT * FROM patents ORDER BY id')).all()
        db.rollback()
        assert run(db,source,True)['inserted']==0
        assert db.execute(text('SELECT * FROM patents ORDER BY id')).all()==before
        db.rollback()
        future=[dict(source[0],number='COPYRIGHT-FUTURE',type='Copyright')]
        assert run(db,future,True)['records'][0]['type']=='COPYRIGHT'
