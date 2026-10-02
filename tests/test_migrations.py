from datetime import date,datetime,timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData,select,text

from backend import db as database
from backend.db import make_engine


def test_patent_upgrade_preserves_existing_publication_authors_evidence(tmp_path,monkeypatch):
    engine=make_engine(f"sqlite:///{tmp_path/'existing.db'}")
    monkeypatch.setattr(database,"engine",engine)
    command.upgrade(Config("alembic.ini"),"63102a78d651")
    old=MetaData();old.reflect(engine)
    timestamp=datetime.now(timezone.utc)
    stamp={"created_at":timestamp,"updated_at":timestamp}
    evidence_path=tmp_path/"existing.pdf";evidence_path.write_bytes(b"preserve this evidence")
    with engine.begin() as connection:
        connection.execute(old.tables["academic_years"].insert(),dict(id=1,name="2026-27",start_date=date(2026,7,1),end_date=date(2027,6,30),**stamp))
        connection.execute(old.tables["faculty"].insert(),dict(id=1,employee_id="A",name="Faculty A",name_variants=[],is_active=True,**stamp))
        connection.execute(old.tables["publications"].insert(),dict(id=1,academic_year_id=1,doi="10.1234/existing",title="Existing research",publication_type="JOURNAL",publication_date=date(2026,9,18),indexing=["SCOPUS"],metadata_source="MANUAL",is_claimable=True,is_active=True,**stamp))
        connection.execute(old.tables["publication_authors"].insert(),dict(id=1,publication_id=1,author_order=1,author_name_from_source="Faculty A",affiliation_from_source=[],person_type="FACULTY",faculty_id=1,is_internal=True,is_claiming_faculty=True,is_corresponding_author=False,is_first_author=True,matching_status="CONFIRMED",**stamp))
        connection.execute(old.tables["evidence_files"].insert(),dict(id=1,publication_id=1,original_filename="existing.pdf",storage_path=str(evidence_path),content_type="application/pdf",size_bytes=22,sha256="a"*64,evidence_type="PUBLICATION_PROOF",**stamp))
    command.upgrade(Config("alembic.ini"),"head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT title FROM publications WHERE id=1"))=="Existing research"
        assert connection.scalar(text("SELECT classification FROM publications WHERE id=1"))=="UNKNOWN"
        assert connection.scalar(text("SELECT indexing FROM publications WHERE id=1"))=='["SCOPUS"]'
        assert connection.scalar(text("SELECT is_claiming_faculty FROM publication_authors WHERE id=1"))==1
        assert connection.scalar(text("SELECT publication_id FROM evidence_files WHERE id=1"))==1
        assert connection.scalar(text("SELECT patent_id FROM evidence_files WHERE id=1")) is None
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall()==[]
        sql=connection.scalar(text("SELECT sql FROM sqlite_master WHERE name='publications'"))
        assert "publication_type_valid" in sql
    assert evidence_path.read_bytes()==b"preserve this evidence"
    engine.dispose()


def test_bibtex_conference_migration_preserves_publications_and_provenance(tmp_path,monkeypatch):
    engine=make_engine(f"sqlite:///{tmp_path/'conference-upgrade.db'}")
    monkeypatch.setattr(database,'engine',engine)
    config=Config('alembic.ini')
    command.upgrade(config,'a72fd081be34')
    old=MetaData();old.reflect(engine)
    stamp={'created_at':datetime.now(timezone.utc),'updated_at':datetime.now(timezone.utc)}
    with engine.begin() as connection:
        connection.execute(old.tables['faculty'].insert(),dict(id=1,employee_id='P',name='Existing Faculty',name_variants=[],name_variant_strengths={},is_active=True,**stamp))
        for i in range(1,130):
            connection.execute(old.tables['publications'].insert(),dict(id=i,doi=f'10.1234/preserved-{i}',title=f'Existing {i}',publication_type='JOURNAL',publication_date=date(2026,9,18),indexing=['SCI'],impact_factor=3.4,quartile='Q1',metadata_source='CROSSREF',remarks='Historical journal import: Journal Excel row 2;' if i>4 else None,is_claimable=True,is_active=True,**stamp))
            connection.execute(old.tables['publication_authors'].insert(),dict(publication_id=i,author_order=1,author_name_from_source='Existing Faculty',affiliation_from_source=[],person_type='FACULTY',faculty_id=1,is_internal=True,is_claiming_faculty=True,is_corresponding_author=False,is_first_author=True,matching_status='EXACT',**stamp))
        originals=connection.execute(text('SELECT * FROM publications ORDER BY id')).fetchall()
    command.upgrade(config,'head')
    names=','.join('"'+c.name+'"' for c in old.tables['publications'].columns)
    with engine.connect() as connection:
        assert connection.execute(text(f'SELECT {names} FROM publications ORDER BY id')).fetchall() == originals
        assert connection.scalar(text("SELECT count(*) FROM publications WHERE source_type='HISTORICAL_EXCEL'")) == 125
        assert connection.scalar(text("SELECT count(*) FROM publications WHERE source_type='DOI'")) == 4
        assert connection.scalar(text('SELECT count(*) FROM publication_authors WHERE is_claiming_faculty=1')) == 129
        assert connection.execute(text('PRAGMA foreign_key_check')).fetchall() == []
    engine.dispose()


def test_books_upgrade_preserves_patent_evidence_and_downgrade_roundtrip(tmp_path,monkeypatch):
    engine=make_engine(f"sqlite:///{tmp_path/'books-upgrade.db'}")
    monkeypatch.setattr(database,"engine",engine)
    config=Config("alembic.ini")
    command.upgrade(config,"2d1933d80295")
    old=MetaData();old.reflect(engine)
    stamp={"created_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)}
    with engine.begin() as connection:
        connection.execute(old.tables["faculty"].insert(),dict(id=1,employee_id="P",name="Patent Faculty",name_variants=[],is_active=True,**stamp))
        connection.execute(old.tables["patents"].insert(),dict(id=1,title="Preserved patent",patent_office="IPO",current_status="FILED",is_claimable=True,is_active=True,**stamp))
        connection.execute(old.tables["patent_inventors"].insert(),dict(id=1,patent_id=1,inventor_order=1,inventor_name="Patent Faculty",person_type="FACULTY",institution_scope="CURRENT_DEPARTMENT",faculty_id=1,is_claiming_faculty=True,**stamp))
        connection.execute(old.tables["evidence_files"].insert(),dict(id=1,patent_id=1,original_filename="proof.pdf",storage_path="2026-27/PATENT/1/proof.pdf",content_type="application/pdf",size_bytes=10,sha256="a"*64,evidence_type="FILING_PROOF",**stamp))
    command.upgrade(config,"head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT title FROM patents WHERE id=1"))=="Preserved patent"
        assert connection.scalar(text("SELECT is_claiming_faculty FROM patent_inventors WHERE id=1"))==1
        assert connection.scalar(text("SELECT patent_id FROM evidence_files WHERE id=1"))==1
        assert connection.scalar(text("SELECT book_record_id FROM evidence_files WHERE id=1")) is None
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall()==[]
    command.downgrade(config,"2d1933d80295")
    command.upgrade(config,"head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT patent_id FROM evidence_files WHERE id=1"))==1
    engine.dispose()
