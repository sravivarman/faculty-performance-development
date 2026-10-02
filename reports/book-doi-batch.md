# Books / Chapters multiple DOI entry

View locally: http://127.0.0.1:3000/books/new

## Multiple DOI Entry

Add by DOI accepts one or many DOIs in the same compact queue. Manual Entry remains available. Switching tabs retains queue entries and an unfinished manual draft. No metadata fetch saves a record.

## Batch Parsing

The shared Publications parser normalizes DOI URLs, doi: prefixes and DOI case, removes blanks and normalized duplicates, and preserves first occurrence order. It accepts newline, comma and semicolon delimiters, plus spaces before recognizable DOI prefixes. Invalid input remains visible with Edit DOI and Remove actions.

## Metadata Queue

Metadata requests run sequentially with progress. Each row independently tracks fetching, readiness, missing claimant, review, duplicate, invalid DOI, lookup failure and saved states. The queue includes type, bibliographic details, matched faculty, claimant, classification and actions. Filters and ten summary counters describe the current deduplicated queue. Desktop and mobile use a contained horizontally scrollable table.

## Auto Type Detection

Existing Books metadata mapping detects Book and Book Chapter from provider metadata. Unresolved type requires review confirmation. Each row allows type correction; required chapter container and page information use existing Books validation.

## Author Matching

Existing master matching and provider metadata mapping preserve contributors, order, author/editor roles and source metadata. UNKNOWN authors remain UNKNOWN and do not block a valid faculty claim. Students remain authors and cannot claim. Missing provider fields can be supplied in the full review editor.

## Claimant Handling

A sole matched active department Faculty AUTHOR is automatically selected. Multiple eligible faculty require a per-record selection. Without an eligible faculty author, the DOI item needs review. No claimant is shared across queue rows. The read-only preview validation endpoint checks real master IDs, bibliographic requirements and exactly one eligible Faculty AUTHOR claimant. Existing manual whole-book editor conventions remain available.

## Duplicate Detection

Normalized duplicates within pasted input appear once. Existing database DOI records show DUPLICATE with the existing record link. Corrected DOI input is checked against the queue and database. Save-time database conflicts also become duplicates, and saved queue items are excluded from retries and readiness counts.

## Bulk Save

Add All Ready, Select All Ready, Save Selected and Clear Selection operate on unsaved eligible records only. Each record uses the existing transactional Books save endpoint. Successful saves update the existing Books dashboard and faculty reporting through the normal domain persistence path.

## Partial Failure Handling

A failed lookup or save does not interrupt other valid items. Failed lookup items support retry or manual completion in the queue; incomplete records support Review / Edit. Successfully saved items remain saved. Evidence uploads occur after the publication save, with Retry Evidence targeting the same saved record when an upload fails.

## Reused Publication Components

Shared DOI parsing and normalization, the Publications parse API, existing Crossref provider, master matching, API error handling, BookEditor, evidence handling and Books persistence are reused. Books retains its own metadata mapping and domain models. No schema migration or Publication/Patent model changes were introduced. The live SQLite table fingerprints are unchanged; see book-doi-batch-data-audit.json.

## Tests

- Backend suite: 266 passed.
- Frontend unit tests: 49 passed.
- All 19 browser cases verified across the full run and corrective focused rerun. The full run initially had 17 passes and two failures; the corrected queue and manual-entry cases subsequently passed together (5 passed).
- Final queue browser rerun after layout refinement: 3 passed.
- Coverage includes single, uniform Book, uniform Chapter and mixed batches; delimiter and URL normalization; duplicates and retry; independent claimants; UNKNOWN authors; invalid and failed lookups; manual completion; evidence; partial save; selection and saved-count exclusion; dashboard counts and faculty relationships.
- Production desktop/mobile smoke verified full Book Chapter label visibility, contained mobile scrolling and draft retention. Metadata was mocked for this visual check; no live records were saved.

## Build Result

Final production build and TypeScript type-check pass. Production app is running at http://127.0.0.1:3000/books/new. Existing live records and claims were preserved.
