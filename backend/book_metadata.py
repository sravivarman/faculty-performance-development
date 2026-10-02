"""Map the shared DOI provider's source record into an editable book preview."""
from sqlalchemy import select

from .matching import match_author
from .models import Faculty, Student

BOOK_TYPES = {'book', 'reference-book', 'edited-book', 'monograph'}
CHAPTER_TYPES = {'book-chapter', 'book-section', 'reference-entry', 'book-part'}
AMBIGUOUS_TYPES = {'book-series', 'book-set', 'book-track', 'other'}


def book_preview(data, db):
    raw = (data.get('raw_metadata_json') or {}).get('message', {})
    source_type = raw.get('type')
    if source_type and source_type not in BOOK_TYPES | CHAPTER_TYPES | AMBIGUOUS_TYPES:
        raise ValueError('This DOI describes a non-book record. Use Publications for journals or conferences, or continue manually with a book DOI.')
    kind = 'BOOK' if source_type in BOOK_TYPES else 'BOOK_CHAPTER' if source_type in CHAPTER_TYPES else None
    faculty = db.scalars(select(Faculty)).all()
    students = db.scalars(select(Student)).all()
    contributors = []
    source_people = [(a, 'AUTHOR') for a in data.get('authors', [])]
    for editor in raw.get('editor') or []:
        source_people.append(({
            'author_name_from_source': editor.get('name') or ' '.join(filter(None, [editor.get('given'), editor.get('family')])),
            'given_name_from_source': editor.get('given'), 'family_name_from_source': editor.get('family'),
            'orcid_from_source': editor.get('ORCID'),
            'affiliation_from_source': [a['name'] for a in editor.get('affiliation') or [] if a.get('name')],
        }, 'EDITOR'))
    for source, role in source_people:
        matched = match_author(source, faculty, students)
        linked = matched.get('person_type') in ('FACULTY', 'STUDENT') and bool(matched.get('faculty_id') or matched.get('student_id'))
        contributors.append({'contributor_order': len(contributors) + 1,
            'contributor_name': source['author_name_from_source'], 'role': role,
            'person_type': matched.get('person_type', 'UNKNOWN') if linked else 'UNKNOWN',
            'institution_scope': 'CURRENT_DEPARTMENT' if linked else 'UNKNOWN',
            'faculty_id': matched.get('faculty_id') if linked else None,
            'student_id': matched.get('student_id') if linked else None,
            'is_claiming_faculty': False, 'source_metadata': {**source,
                'matching_status': matched.get('matching_status', 'UNMATCHED'), 'suggestions': matched.get('suggestions', [])}})
    eligible = [c for c in contributors if c['role'] == 'AUTHOR' and c['faculty_id']]
    if len(eligible) == 1:
        eligible[0]['is_claiming_faculty'] = True
    typed = {v.get('type'): v.get('value') for v in raw.get('isbn-type') or []}
    untyped = raw.get('ISBN') or []
    years = [(raw.get(key) or {}).get('date-parts') for key in ('published', 'published-print', 'published-online', 'issued')]
    year = next((parts[0][0] for parts in years if parts and parts[0]), None)
    result = {'doi': data['doi'], 'title': data.get('title', ''), 'publisher': data.get('publisher'),
        'publication_date': data.get('publication_date'), 'publication_year': year,
        'parent_book_title': data.get('journal_conference_name') if kind != 'BOOK' else None,
        'isbn': typed.get('print') or (untyped[0] if untyped and not typed else None),
        'eisbn': typed.get('electronic'), 'edition': str(raw['edition-number']) if raw.get('edition-number') is not None else None, 'volume': data.get('volume'),
        'page_range': data.get('pages_or_article_number') if kind != 'BOOK' else None,
        'url': data.get('url'), 'classification': 'UNKNOWN', 'contributors': contributors,
        'metadata_source': data.get('metadata_source', 'CROSSREF'), 'metadata_fetched_at': data.get('metadata_fetched_at'),
        'raw_metadata_json': data.get('raw_metadata_json'), 'source_type': source_type,
        'warnings': [] if kind else ['The provider did not identify Book or Book Chapter clearly. Select the type before saving.']}
    if kind:
        result['work_type'] = kind
    if year and not data.get('publication_date'):
        result['warnings'].append('Only a publication year was returned. Enter the actual publication date; no day has been assumed.')
    return result
