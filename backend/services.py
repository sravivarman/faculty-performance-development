from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from .matching import normalized_name
from .models import AcademicYear, ChangeLog, Faculty, Publication, PublicationAuthor, Student, now
from .periods import period_bounds
from .schemas import PublicationInput
from .reporting import validate_date_range


def columns(obj):
    values = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    # SQLite drops timezone offsets on load; timestamps are stored in UTC.
    return {key: value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value
            for key, value in values.items()}


def publication_dict(pub, db):
    authors = []
    faculty_ids, student_ids = set(), set()
    for a in pub.authors:
        person = db.get(Faculty, a.faculty_id) if a.faculty_id else db.get(Student, a.student_id) if a.student_id else None
        authors.append({**columns(a), "person_name": person.name if person else None})
        if a.faculty_id:
            faculty_ids.add(a.faculty_id)
        if a.student_id:
            student_ids.add(a.student_id)
    external = sum(a.person_type == "EXTERNAL" for a in pub.authors)
    classifications = []
    if faculty_ids and student_ids:
        classifications.append("Faculty + Student paper")
        if any(a.person_type == "STUDENT" and a.is_first_author for a in pub.authors):
            classifications.append("Student + Faculty paper")
    elif faculty_ids:
        classifications.append("Faculty-only paper")
    elif student_ids:
        classifications.append("Student-only paper")
    if external and (faculty_ids or student_ids):
        classifications.append("External collaboration paper")
    return {
        **columns(pub), "authors": authors,
        "evidence": [{k: v for k, v in columns(e).items() if k != "storage_path"} for e in pub.evidence],
        "evidence_count": len(pub.evidence), "has_internal_faculty": bool(faculty_ids),
        "has_internal_students": bool(student_ids), "internal_faculty_count": len(faculty_ids),
        "internal_student_count": len(student_ids), "external_author_count": external,
        "classifications": classifications,
    }


def save_publication(db, data: PublicationInput, pub=None):
    if data.doi:
        existing = db.scalar(select(Publication).where(Publication.doi == data.doi))
        if existing and (pub is None or existing.id != pub.id):
            raise HTTPException(409, {"message": "Publication already exists.", "publication_id": existing.id})
    else:
        possible = db.scalars(select(Publication).where(Publication.publication_date.between(
            data.publication_date.replace(month=1, day=1), data.publication_date.replace(month=12, day=31)
        ))).all()
        duplicates = [p.id for p in possible if (not pub or p.id != pub.id) and normalized_name(p.title) == normalized_name(data.title)
                      and normalized_name(p.journal_conference_name) == normalized_name(data.journal_conference_name)]
        if duplicates and not data.duplicate_acknowledged:
            raise HTTPException(409, {"message": "Possible duplicate title, year and venue. Review before saving separately.", "possible_duplicate_ids": duplicates})
    years = db.scalars(select(AcademicYear).where(AcademicYear.start_date <= data.publication_date, AcademicYear.end_date >= data.publication_date)).all()
    for author in data.authors:
        for model, identity in ((Faculty, author.faculty_id), (Student, author.student_id)):
            if identity and not db.get(model, identity):
                raise HTTPException(422, f"Unknown {model.__name__} id {identity}")
        if author.is_claiming_faculty:
            person = db.get(Faculty, author.faculty_id)
            previous_claim = pub and any(a.faculty_id == author.faculty_id and a.is_claiming_faculty for a in pub.authors)
            if not person.is_active and not previous_claim:
                raise HTTPException(422, "Select an active department faculty author as the claimant")
    values = data.model_dump(exclude={"authors", "duplicate_acknowledged"})
    provenance = {"CROSSREF": "DOI", "BIBTEX": "BIBTEX", "BIBTEX_PLUS_DOI": "BIBTEX_PLUS_DOI"}
    if pub is None and "source_type" not in data.model_fields_set:
        values["source_type"] = provenance.get(data.metadata_source, "MANUAL")
    if pub is not None:
        if "classification" not in data.model_fields_set:
            values.pop("classification", None)
        for key in ("source_type", "raw_bibtex", "conference_name", "proceedings_title", "conference_start_date",
                    "conference_end_date", "conference_location", "conference_organizer"):
            if key not in data.model_fields_set:
                values.pop(key, None)
    # Clients predating the historical impact-factor field omit it on edits.
    # Preserve stored values; an explicit null still clears the field.
    if pub is not None and "impact_factor" not in data.model_fields_set:
        values.pop("impact_factor", None)
    values["academic_year_id"] = years[0].id if len(years) == 1 else None
    before = publication_dict(pub, db) if pub else None
    if pub is None:
        pub = Publication(**values)
        db.add(pub)
        db.flush()
    else:
        for key, value in values.items():
            setattr(pub, key, value)
        # Flush deletion before insertion so changing the claimant is atomic and
        # cannot temporarily violate the partial unique index.
        pub.authors.clear()
        db.flush()
        pub.updated_at = now()
    pub.authors = [PublicationAuthor(**a.model_dump()) for a in data.authors]
    db.flush()
    after = publication_dict(pub, db)
    db.add(ChangeLog(publication_id=pub.id, action="UPDATE" if before else "CREATE", changes=jsonable_encoder({"before": before, "after": after})))
    db.commit()
    return pub


def filtered_publications(db, from_date=None, to_date=None,
                          faculty_id=None, student_id=None, student_participation=None,
                          indexing=None, publication_type=None, metric=None, include_inactive=False,
                          drill_faculty_id=None, drill_student_id=None, claiming_faculty_id=None, quartile=None, classification=None, dashboard_only=False):
    from .publication_reporting import publication_query
    selected = {key: value for key, value in locals().items() if key != 'db'}
    return db.scalars(publication_query(**selected).order_by(Publication.publication_date.desc(), Publication.id.desc())).all()


def department_kpis(pubs):
    return {
        "total": len(pubs), "journal": sum(p.publication_type == "JOURNAL" for p in pubs),
        "conference": sum(p.publication_type == "CONFERENCE" for p in pubs),
        "scopus": sum("SCOPUS" in p.indexing for p in pubs),
        "web_of_science": sum("WEB_OF_SCIENCE" in p.indexing for p in pubs),
        "sci_scie": sum(bool(set(p.indexing) & {"SCI", "SCIE"}) for p in pubs),
        "sci": sum("SCI" in p.indexing for p in pubs),
        "scie": sum("SCIE" in p.indexing for p in pubs),
        "esci": sum("ESCI" in p.indexing for p in pubs),
        "ugc_care": sum("UGC_CARE" in p.indexing for p in pubs),
        **{f"{scope.lower()}_{kind.lower()}": sum(p.classification == scope and p.publication_type == kind for p in pubs)
           for scope in ("INTERNATIONAL", "NATIONAL") for kind in ("JOURNAL", "CONFERENCE")},
        **{q.lower(): sum(p.quartile == q for p in pubs) for q in ["Q1", "Q2", "Q3", "Q4"]},
        "with_students": sum(any(a.student_id for a in p.authors) for p in pubs),
        "without_students": sum(not any(a.student_id for a in p.authors) for p in pubs),
        "unique_faculty": len({a.faculty_id for p in pubs for a in p.authors if a.faculty_id}),
        "unique_students": len({a.student_id for p in pubs for a in p.authors if a.student_id}),
    }


def faculty_kpis(db, pubs):
    return [{"id": f.id, "name": f.name,
             "claimed": sum(any(a.faculty_id == f.id and a.is_claiming_faculty for a in p.authors) for p in pubs),
             "authored": sum(any(a.faculty_id == f.id for a in p.authors) for p in pubs),
             **{scope.lower(): sum(p.classification == scope and any(a.faculty_id == f.id for a in p.authors) for p in pubs) for scope in ("INTERNATIONAL", "NATIONAL")},
             **{tag.lower(): sum(tag in p.indexing and any(a.faculty_id == f.id for a in p.authors) for p in pubs) for tag in ("SCI", "SCIE", "SCOPUS", "WEB_OF_SCIENCE", "ESCI", "UGC_CARE")},
             **{f"{kind}_{role}": sum(p.publication_type == kind.upper() and any(a.faculty_id == f.id and
                  (role == "authored" or a.is_claiming_faculty) for a in p.authors) for p in pubs)
                for kind in ("journal", "conference") for role in ("claimed", "authored")}}
            for f in db.scalars(select(Faculty).order_by(Faculty.name))]


def student_kpis(db, pubs):
    result = []
    for student in db.scalars(select(Student).order_by(Student.name)):
        authored = [p for p in pubs if any(a.student_id == student.id for a in p.authors)]
        collaborators = sorted({a.faculty_id for p in authored for a in p.authors if a.faculty_id})
        result.append({"id": student.id, "name": student.name, "authored": len(authored),
                       "journal": sum(p.publication_type == "JOURNAL" for p in authored),
                       "conference": sum(p.publication_type == "CONFERENCE" for p in authored),
                       "indexed": sum(bool(set(p.indexing) - {"NONE", "UNKNOWN"}) for p in authored),
                       "faculty_collaborators": [{"id": i, "name": db.get(Faculty, i).name} for i in collaborators]})
    return result

