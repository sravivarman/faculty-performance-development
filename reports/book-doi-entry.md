# Books / Chapters DOI entry completion

## DOI Entry Added

Open http://127.0.0.1:3000/books/new. **Add by DOI** and **Manual Entry** share the existing editable review form. Fetching never writes a record. Saving creates a normal Books / Chapters record; there is no additional import status or BibTeX workflow.

## DOI Field Enabled

DOI is editable and optional for both types, including manual entry and editing. Bare DOIs, doi.org URLs, dx.doi.org URLs and `doi:` prefixes use the existing Publications normalizer. Storage uses the normalized lowercase identifier. DOI and ISBN remain independent.

## Metadata Provider Reused

The existing `CrossrefProvider`, HTTP request implementation, parsing and DOI normalization are reused. `/book-metadata` now maps book metadata, matches contributors and checks duplicates against the actual Books table. It does not call the Publication creation endpoint. Provider and fetched timestamp, the raw response and contributor source metadata are preserved using the same provenance pattern as Publications. Crossref exposes metadata deposited by its members and trusted sources; see its [REST API documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).

## Supported DOI Types

- Book: `book`, `reference-book`, `edited-book`, `monograph`.
- Book Chapter: `book-chapter`, `book-section`, `reference-entry`, `book-part`.
- Ambiguous: `book-series`, `book-set`, `book-track`, `other`, or missing type require explicit type confirmation before UI saving.

Known journal, conference and other non-book types are rejected with a clear message. Reviewers may correct the selected type. The workflow never creates a Journal or Conference record.

## Book Mapping

Title, normalized DOI, publisher, full publication date when provided, source publication year, authors, editors, ISBN/eISBN, edition, volume and source URL. Typed ISBN values are used when supplied. An untyped ISBN is retained in ISBN without inventing an electronic designation. Classification is reviewed independently and is never inferred from publisher or DOI.

## Book Chapter Mapping

Chapter title, parent/container book title and pages are mapped in addition to the shared bibliographic fields. The existing editable `page_range` field preserves supplied start/end pages together; separate page columns are unnecessary. Edition and volume are now available for chapters too. The existing chapter requirements—parent title, page range and an author—remain in force.

## Author Matching

Authors retain source order; editors retain their separate role and source order. Existing Faculty/Student name, approved variant and ORCID matching is reused. Ambiguous, weak and fuzzy suggestions require manual confirmation. No master record is automatically created. UNKNOWN contributors do not block saving. Source names, given/family names, ORCID and affiliation are retained in contributor source metadata. Manual classification uses the module's existing `EXTERNAL_PERSON` representation for external people.

## Claiming Faculty

A sole matched department Faculty author is automatically selected. Multiple Faculty authors require a choice; no match requires manual mapping. New records require exactly one valid mapped Faculty claimant, with an active Faculty Master record. Student, UNKNOWN and external contributors cannot claim. A chapter claimant must be a chapter author. Existing whole-book editor participation/claim conventions remain supported without counting an editor as an author. Historical unclaimed records remain readable and editable; previously claimed records cannot lose their required single claim.

## Duplicate Detection

Normalized DOI duplicates are blocked across Books and Chapters, including inactive records, both before lookup and on save. A duplicate response supplies the existing record ID and a **View Existing** link. The unique database index also protects simultaneous saves; the conflict handler rolls back and supplies the existing record link. Existing no-DOI title/year/ISBN duplicate review remains available.

## Manual Fallback

Failed lookups retain the entered DOI and show a non-blocking manual-entry message. Available metadata is editable; missing values remain blank. DOI-only, ISBN-only, both identifiers and neither identifier are supported when remaining requirements and the Faculty claim are valid. Evidence remains optional under current module rules. Review confirmation is still required.

## Dashboard Integration

Saved records use the existing list, Books overview, Research overview, faculty contribution and faculty profile aggregations. One work counts once for the department. Claims and authored counts stay separate, including multi-Faculty chapters. Classification is now stored explicitly and shown in Books classification charts and International/National cards. Historical missing classification counts as Unknown; historical values are not backfilled or inferred.

## Tests

- 254 tests passed in the full backend regression suite. Final book DOI checks: 20 passed, including one subsequently added simultaneous-save conflict test and stronger historical contributor preservation assertions (255 distinct backend cases verified).
- All 46 frontend unit tests passed, including claimant eligibility and UNKNOWN/Student non-blocking behavior.
- Full browser run: 18 cases passed; an ambiguous-type confirmation checkbox failure was fixed. The final three DOI browser cases all passed, bringing all 19 distinct browser cases to passing results across these runs.
- Browser coverage includes automatic chapter detection, UNKNOWN persistence, single-Faculty selection, multiple-Faculty selection, incomplete/ambiguous review, duplicate links and failed lookup with manual completion. Existing manual book, evidence, dashboard, Publication DOI/multiple DOI/BibTeX and master flows passed.
- Production smoke check verified desktop/mobile review, enabled save with an UNKNOWN contributor and no browser errors. The smoke check did not save a live record.

## Build Result

TypeScript type-check and Next.js production build passed. The production app and backend were restarted with the completed implementation.

Migration `f20a3dc817ab` adds optional classification, volume/year and provenance/source metadata columns. The existing DOI field and unique constraint are reused. Before applying it to `data/faculty.db`, a SQLite backup was created at `data/backups/faculty-before-book-doi-20261002-225841.db`. Verification confirmed all existing values and relationships across 14 tables remained identical, including 325 Publications; no live Book records were created. See [migration verification](book-doi-migration-audit.json). Tests also verify preservation of a historical Book and its Faculty claim. A downgrade is allowed only when the added fields contain no data, protecting stored provenance.

## Metadata Limitations

Crossref may omit authors, editors, ISBN media types, container title, pages or a complete date. Missing information must be completed manually where required. Partial year/month dates are not expanded into invented days. Editors returned for a chapter are retained under the module's parent-book editor convention; no additional parent DOI lookup is attempted. Classification is not inferred. ISBNs returned by a provider remain subject to existing checksum validation and can be corrected during review. Tests use deterministic provider responses; no user-supplied real Book DOI was available for a live-provider acceptance check.
