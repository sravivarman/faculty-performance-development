"""BibTeX preview parsing; never writes publications or master records."""
from datetime import date

import bibtexparser
from bibtexparser import middlewares as m
from bibtexparser.model import Entry, ParsingFailedBlock
from pylatexenc.latex2text import LatexNodes2Text
from sqlalchemy import select

from .doi import normalize_doi
from .matching import match_author, normalized_name
from .metadata import MetadataError
from .models import Faculty, Publication, Student


class BibTeXPublicationParser:
    types = {'article': 'JOURNAL', 'inproceedings': 'CONFERENCE', 'conference': 'CONFERENCE'}

    def parse(self, content, db, provider, enrich=True):
        library = bibtexparser.parse_string(content, append_middleware=[m.SeparateCoAuthors(), m.SplitNameParts()])
        faculty, students = list(db.scalars(select(Faculty))), list(db.scalars(select(Student)))
        publications = list(db.scalars(select(Publication)))
        decoder = LatexNodes2Text()
        results, cache, seen_dois, seen_titles = [], {}, {}, {}
        for block in library.blocks:
            if not isinstance(block, (Entry, ParsingFailedBlock)):
                continue
            number = len(results) + 1
            item = {'entry_number': number, 'citation_key': getattr(block, 'key', None), 'raw_bibtex': block.raw,
                    'line': block.start_line + 1, 'status': 'PARSE_ERROR', 'errors': [], 'warnings': [],
                    'duplicate_ids': [], 'duplicate_entry': None, 'differences': [], 'publication': None}
            results.append(item)
            if isinstance(block, ParsingFailedBlock):
                item['errors'] = [f'Entry {number} could not be parsed near line {block.start_line+1}. Check braces, quotes and field separators. {block.error}']
                continue
            try:
                fields = {key: field.value for key, field in block.fields_dict.items()}
                def value(key):
                    raw = fields.get(key)
                    if key in {'doi', 'url', 'issn', 'isbn', 'pages', 'volume', 'number', 'year', 'month',
                               'date', 'conference_start_date', 'conference_end_date'}:
                        return str(raw).strip() if raw is not None else None
                    return decoder.latex_to_text(str(raw)).strip() if raw is not None else None
                kind = self.types.get(block.entry_type.casefold())
                draft = {'title': value('title') or '', 'doi': None, 'publication_type': kind or 'OTHER',
                         'journal_conference_name': value('journal') if kind == 'JOURNAL' else value('booktitle'),
                         'publisher': value('publisher'), 'volume': value('volume'), 'issue': value('number'),
                         'pages_or_article_number': value('pages'), 'issn': value('issn'), 'isbn': value('isbn'),
                         'url': value('url'), 'publication_date': None, 'indexing': [], 'impact_factor': None,
                         'quartile': None, 'source_type': 'BIBTEX', 'metadata_source': 'BIBTEX',
                         'raw_bibtex': block.raw, 'is_claimable': True, 'is_active': True, 'authors': [],
                         'raw_metadata_json': {'bibtex': {'entry_type': block.entry_type, 'key': block.key,
                                               'fields': {key: str(field.value) for key, field in block.fields_dict.items()}}}}
                if kind == 'CONFERENCE':
                    draft.update(proceedings_title=value('booktitle'), conference_name=value('eventtitle'),
                                 conference_location=value('address') or value('venue'), conference_organizer=value('organization'))
                    for key in ['conference_start_date', 'conference_end_date']:
                        if fields.get(key):
                            try: draft[key] = date.fromisoformat(value(key)).isoformat()
                            except ValueError: item['warnings'].append(f'{key} is not an exact date; complete it manually.')
                if not kind:
                    item['warnings'].append(f'Unsupported BibTeX type @{block.entry_type}; choose Journal or Conference after manual review.')
                year = value('year')
                item['publication_year'], item['publication_month'] = year, value('month')
                if value('date'):
                    try: draft['publication_date'] = date.fromisoformat(value('date')).isoformat()
                    except ValueError: item['warnings'].append('BibTeX date is partial or invalid; supply an exact publication date.')
                if value('doi'):
                    try:
                        # Prefix nesting is common in website exports.
                        raw_doi = value('doi').strip()
                        if raw_doi.lower().startswith('doi:'): raw_doi = raw_doi[4:].strip()
                        draft['doi'] = normalize_doi(raw_doi)
                    except ValueError as exc: item['errors'].append(str(exc))
                for order, name in enumerate(fields.get('author') or [], 1):
                    first = decoder.latex_to_text(' '.join(name.first))
                    last = decoder.latex_to_text(' '.join(name.von + name.last))
                    suffix = decoder.latex_to_text(' '.join(name.jr))
                    source_name = ' '.join(filter(None, [first, last, suffix]))
                    draft['authors'].append({'author_order': order, 'author_name_from_source': source_name,
                                             'given_name_from_source': first or None, 'family_name_from_source': last or None,
                                             'orcid_from_source': None, 'affiliation_from_source': [], 'person_type': 'UNKNOWN',
                                             'faculty_id': None, 'student_id': None, 'is_internal': False,
                                             'is_claiming_faculty': False, 'is_first_author': order == 1,
                                             'is_corresponding_author': False, 'matching_status': 'UNMATCHED'})
                if draft['doi']:
                    item['duplicate_ids'] = [p.id for p in publications if p.doi == draft['doi']]
                    item['duplicate_entry'] = seen_dois.get(draft['doi'])
                    seen_dois[draft['doi']] = number
                duplicate_key = (normalized_name(draft['title']), year, normalized_name(draft['journal_conference_name']))
                if not draft['doi'] and draft['title'] and year and draft['journal_conference_name']:
                    item['duplicate_ids'] = [p.id for p in publications if normalized_name(p.title) == duplicate_key[0]
                                             and str(p.publication_date.year) == year and normalized_name(p.journal_conference_name) == duplicate_key[2]]
                    item['duplicate_entry'] = seen_titles.get(duplicate_key)
                    seen_titles[duplicate_key] = number
                if draft['doi'] and enrich and not item['duplicate_ids'] and not item['duplicate_entry']:
                    try:
                        if draft['doi'] not in cache:
                            try: cache[draft['doi']] = provider.fetch_by_doi(draft['doi'])
                            except MetadataError as exc: cache[draft['doi']] = exc
                        metadata = cache[draft['doi']]
                        if isinstance(metadata, MetadataError): raise metadata
                        if normalize_doi(metadata['doi']) != draft['doi']: raise MetadataError('DOI provider returned a different identifier')
                        metadata = dict(metadata, authors=[dict(match_author(a, faculty, students), is_claiming_faculty=False) for a in metadata.get('authors', [])])
                        for key, enriched in metadata.items():
                            if key in {'doi', 'indexing', 'impact_factor', 'quartile', 'metadata_source', 'raw_metadata_json', 'metadata_fetched_at'}:
                                continue
                            if enriched is None or enriched == '' or enriched == []: continue
                            if draft.get(key) is None or draft.get(key) == '' or draft.get(key) == []:
                                draft[key] = enriched
                            elif draft[key] != enriched:
                                item['differences'].append({'field': key, 'bibtex': draft[key], 'doi': enriched})
                        draft['metadata_fetched_at'] = metadata.get('metadata_fetched_at')
                        draft['raw_metadata_json']['doi_metadata'] = metadata.get('raw_metadata_json')
                        draft.update(source_type='BIBTEX_PLUS_DOI', metadata_source='BIBTEX_PLUS_DOI')
                    except MetadataError as exc:
                        item['warnings'].append('DOI enrichment unavailable; BibTeX remains editable. ' + str(exc))
                draft['authors'] = [dict(match_author(a, faculty, students), is_claiming_faculty=False) for a in draft['authors']]
                item['publication'] = draft
                if item['errors']: item['status'] = 'PARSE_ERROR'
                elif item['duplicate_ids'] or item['duplicate_entry']: item['status'] = 'DUPLICATE'
                elif not kind or not draft['title']: item['status'] = 'AUTHOR_REVIEW'
                elif not draft['publication_date']: item['status'] = 'MISSING_DATE'
                elif any(a['matching_status'] == 'SUGGESTED' for a in draft['authors']): item['status'] = 'AUTHOR_REVIEW'
                else: item['status'] = 'NEEDS_CLAIMANT'
            except Exception as exc:
                item['errors'] = [f'Entry {number} could not be converted: {type(exc).__name__}: {exc}. Review this entry.']
                item['status'] = 'PARSE_ERROR'
        return {'entries': results, 'total_entries': len(results)}
