"""Read-only queue validation using the same schemas and masters as book saves."""
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from .book_schemas import BookInput
from .book_services import book_dict
from .doi import normalize_doi
from .models import BookPublication, Faculty, Student


class BookPreviewInput(BaseModel):
    draft: dict
    type_resolved: bool = False


def validate_preview(db, draft, type_resolved):
    doi = None
    def result(status, errors=None, **values):
        return {'status': status, 'errors': errors or [], 'doi': doi, **values}
    try:
        doi = normalize_doi(draft.get('doi'))
        if not doi:
            raise ValueError('A DOI is required for a DOI queue item. Use Manual Entry for records without a DOI.')
    except ValueError as exc:
        return result('INVALID_DOI', [str(exc)])
    existing = db.scalar(select(BookPublication).where(BookPublication.doi == doi))
    if existing:
        return result('DUPLICATE', ['A Book / Chapter with this DOI already exists.'], existing=book_dict(existing, db))
    if not type_resolved:
        return result('NEEDS_REVIEW', ['Select Book or Book Chapter explicitly.'])
    try:
        data = BookInput.model_validate({**draft, 'doi': doi})
    except ValidationError as exc:
        return result('NEEDS_REVIEW', [f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors()])
    for c in data.contributors:
        for model, identity in ((Faculty, c.faculty_id), (Student, c.student_id)):
            if identity is not None and db.get(model, identity) is None:
                return result('NEEDS_REVIEW', [f'Unknown {model.__name__} master reference.'])
    faculty = [c for c in data.contributors if c.role == 'AUTHOR' and c.person_type == 'FACULTY'
               and c.institution_scope == 'CURRENT_DEPARTMENT' and c.faculty_id and db.get(Faculty, c.faculty_id).is_active]
    if not faculty:
        return result('NEEDS_REVIEW', ['Map at least one current-department Faculty author.'])
    claimants = [c for c in data.contributors if c.is_claiming_faculty]
    if len(claimants) != 1 or claimants[0] not in faculty:
        return result('NEEDS_CLAIMANT', ['Select exactly one current-department Faculty author as claimant.'])
    return result('READY', draft=data.model_dump(mode='json'))
