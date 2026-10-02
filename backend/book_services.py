from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from .book_schemas import normalize_isbn
from .matching import normalized_name
from .models import BookPublication, BookContributor, BookChangeLog, Faculty, Student, now
from .services import columns


def person_key(c):
    return (c.person_type, c.faculty_id or c.student_id or normalized_name(c.employee_or_roll_number or c.contributor_name))


def authors(work, kind=None):
    return [c for c in work.contributors if c.role == "AUTHOR" and c.is_current_department and (not kind or c.person_type == kind)]


def participants(work, kind=None):
    """Whole-book editors qualify; parent-book editors alone do not imply chapter participation."""
    return [c for c in work.contributors if c.is_current_department and (work.work_type == 'BOOK' or c.role == 'AUTHOR') and (not kind or c.person_type == kind)]


def department_work(work):
    return any(c.is_current_department and (work.work_type == "BOOK" or c.role == "AUTHOR") for c in work.contributors)


def indicators(work):
    # Parent-book editors are retained but do not imply chapter participation.
    participants = [c for c in work.contributors if work.work_type == "BOOK" or c.role == "AUTHOR"]
    local = [c for c in participants if c.is_current_department]
    other = [c for c in participants if c.institution_scope == "SAME_INSTITUTION_OTHER_DEPARTMENT"]
    external = [c for c in participants if c.institution_scope == "EXTERNAL_INSTITUTION"]
    faculty = {person_key(c) for c in local if c.person_type == "FACULTY"}
    students = {person_key(c) for c in local if c.person_type == "STUDENT"}
    return {"has_current_department_student": bool(students), "has_other_department_contributor": bool(other),
            "has_external_contributor": bool(external), "current_department_faculty_count": len(faculty),
            "current_department_student_count": len(students), "same_institution_other_department_count": len({person_key(c) for c in other}),
            "external_contributor_count": len({person_key(c) for c in external})}


def book_dict(work, db):
    contributors = []
    for c in work.contributors:
        person = db.get(Faculty, c.faculty_id) if c.faculty_id else db.get(Student, c.student_id) if c.student_id else None
        contributors.append({**columns(c), "person_name": person.name if person else None,
                             "is_current_department": c.is_current_department, "is_internal_institution": c.is_internal_institution})
    return {**columns(work), **indicators(work), "contributors": contributors, "evidence_count": len(work.evidence),
            "evidence": [{k: v for k, v in columns(e).items() if k != "storage_path"} for e in work.evidence]}


def save_book(db, data, work=None):
    if (work is None or any(c.is_claiming_faculty for c in work.contributors)) and sum(c.is_claiming_faculty for c in data.contributors) != 1:
        raise HTTPException(422, 'Select exactly one mapped current-department Faculty claimant.')
    if data.doi:
        existing = db.scalar(select(BookPublication).where(BookPublication.doi == data.doi))
        if existing and (not work or existing.id != work.id):
            raise HTTPException(409, {"message": "A Book / Chapter with this DOI already exists.", "book_id": existing.id})
    else:
        isbn, eisbn = normalize_isbn(data.isbn), normalize_isbn(data.eisbn)
        duplicates = [p.id for p in db.scalars(select(BookPublication)) if (not work or p.id != work.id)
                      and p.work_type == data.work_type and normalized_name(p.title) == normalized_name(data.title)
                      and normalized_name(p.parent_book_title or "") == normalized_name(data.parent_book_title or "")
                      and p.publication_date.year == data.publication_date.year
                      and (not (isbn or eisbn) or not (p.normalized_isbn or p.normalized_eisbn)
                           or bool(({isbn, eisbn} - {None}) & ({p.normalized_isbn, p.normalized_eisbn} - {None})))]
        if duplicates and not data.duplicate_acknowledged:
            raise HTTPException(409, {"message": "Possible duplicate: title, book, ISBN and publication year match. Review before saving separately.",
                                     "possible_duplicate_ids": duplicates})
    for c in data.contributors:
        for model, identity in ((Faculty, c.faculty_id), (Student, c.student_id)):
            if identity is not None:
                person = db.get(model, identity)
                if not person:
                    raise HTTPException(422, f"Unknown {model.__name__} id {identity}")
                if work is None and c.is_claiming_faculty and not person.is_active:
                    raise HTTPException(422, 'The claiming Faculty must be active in Faculty Master.')
                if not c.employee_or_roll_number:
                    c.employee_or_roll_number = person.employee_id if model is Faculty else person.roll_number
    before = book_dict(work, db) if work else None
    values = data.model_dump(exclude={"contributors", "duplicate_acknowledged"})
    values.update(normalized_isbn=normalize_isbn(data.isbn), normalized_eisbn=normalize_isbn(data.eisbn))
    if work is None:
        work = BookPublication(**values)
        db.add(work)
        db.flush()
    else:
        for key, value in values.items():
            setattr(work, key, value)
        work.contributors.clear()
        db.flush()
        work.updated_at = now()
    work.contributors = [BookContributor(**c.model_dump()) for c in data.contributors]
    db.flush()
    db.add(BookChangeLog(book_record_id=work.id, action="UPDATE" if before else "CREATE",
                         changes=jsonable_encoder({"before": before, "after": book_dict(work, db)})))
    db.commit()
    return work


def selected_books(db, from_date=None, to_date=None, work_type=None, faculty_id=None, student_id=None,
                   student_participation=None, interdepartmental=None, external_collaboration=None,
                   publisher=None, isbn_search=None, include_inactive=False, department_only=True):
    query = select(BookPublication).order_by(BookPublication.publication_date.desc(), BookPublication.id.desc())
    if not include_inactive:
        query = query.where(BookPublication.is_active.is_(True))
    if from_date:
        query = query.where(BookPublication.publication_date >= from_date, BookPublication.publication_date <= to_date)
    if work_type:
        query = query.where(BookPublication.work_type == work_type)
    if publisher:
        query = query.where(BookPublication.publisher == publisher)
    works = db.scalars(query).all()
    if department_only:
        works = [w for w in works if department_work(w)]
    for identity, field in ((faculty_id, "faculty_id"), (student_id, "student_id")):
        if identity is not None:
            works = [w for w in works if any(getattr(c, field) == identity and c.is_current_department for c in w.contributors)]
    if isbn_search:
        import re
        term = re.sub(r"[\s-]", "", isbn_search).upper()
        try:
            canonical = normalize_isbn(isbn_search)
        except ValueError:
            canonical = None
        works = [w for w in works if any(term in re.sub(r"[\s-]", "", v or "").upper()
                                       for v in (w.isbn, w.eisbn, w.normalized_isbn, w.normalized_eisbn))
                 or (canonical is not None and canonical in (w.normalized_isbn, w.normalized_eisbn))]
    for value, flag in ((student_participation, "has_current_department_student"), (interdepartmental, "has_other_department_contributor"),
                        (external_collaboration, "has_external_contributor")):
        if value is not None:
            works = [w for w in works if indicators(w)[flag] == value]
    return works


def drilldown(works, metric="total", faculty_id=None, student_id=None):
    if faculty_id is not None or student_id is not None:
        works = [w for w in works if any(c.is_current_department and
                 (c.faculty_id == faculty_id if faculty_id is not None else c.student_id == student_id)
                 and (c.is_claiming_faculty if "claimed" in metric else (c in participants(w) if metric == 'participated' else c.role == "AUTHOR")) for c in w.contributors)]
    conditions = {
        **{key.lower(): lambda w, value=key: w.classification == value if value != 'UNKNOWN' else w.classification in (None, 'UNKNOWN') for key in ('INTERNATIONAL', 'NATIONAL', 'OTHER', 'UNKNOWN')},
        "total": lambda w: True, "books": lambda w: w.work_type == "BOOK", "chapters": lambda w: w.work_type == "BOOK_CHAPTER",
        "with_students": lambda w: indicators(w)["has_current_department_student"],
        "interdepartmental": lambda w: indicators(w)["has_other_department_contributor"],
        "external_collaboration": lambda w: indicators(w)["has_external_contributor"],
        "unique_faculty": lambda w: bool(authors(w, "FACULTY")), "unique_students": lambda w: bool(authors(w, "STUDENT")),
        "faculty_contributors": lambda w: any(c.faculty_id for c in participants(w, 'FACULTY')),
        "claimed": lambda w: any(c.is_claiming_faculty for c in w.contributors),
        "authored": lambda w: bool(authors(w)),
        "participated": lambda w: bool(participants(w)),
        "books_claimed": lambda w: w.work_type == "BOOK" and any(c.is_claiming_faculty for c in w.contributors),
        "chapters_claimed": lambda w: w.work_type == "BOOK_CHAPTER" and any(c.is_claiming_faculty for c in w.contributors),
        "books_authored": lambda w: w.work_type == "BOOK" and bool(authors(w)),
        "chapters_authored": lambda w: w.work_type == "BOOK_CHAPTER" and bool(authors(w)),
    }
    if metric not in conditions:
        raise HTTPException(422, "Unknown Books KPI metric")
    return [w for w in works if conditions[metric](w)]


def book_kpis(works):
    return {**{k: len(drilldown(works, k)) for k in ("total", "books", "chapters", "with_students", "interdepartmental", "external_collaboration")},
            "unique_faculty": len({person_key(c) for w in works for c in authors(w, "FACULTY")}),
            "unique_students": len({person_key(c) for w in works for c in authors(w, "STUDENT")})}


def person_kpis(db, works, kind):
    result = []
    for person in db.scalars(select(Faculty if kind == "faculty" else Student).order_by((Faculty if kind == "faculty" else Student).name)):
        identity = {"faculty_id" if kind == "faculty" else "student_id": person.id}
        metrics = ("books_claimed", "books_authored", "chapters_claimed", "chapters_authored", "claimed", "authored", "participated") if kind == "faculty" else ("books_authored", "chapters_authored", "authored")
        row = {"id": person.id, "name": person.name, **{k: len(drilldown(works, k, **identity)) for k in metrics}}
        if kind == "students":
            related = drilldown(works, "authored", student_id=person.id)
            ids = {c.faculty_id for w in related for c in authors(w, "FACULTY") if c.faculty_id is not None}
            row.update(roll_number=person.roll_number, total_works=row["authored"],
                       faculty_collaborators=[{"id": i, "name": db.get(Faculty, i).name} for i in sorted(ids)])
        result.append(row)
    return result
