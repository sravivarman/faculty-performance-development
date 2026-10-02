# Faculty publication management

A single-department publication and KPI application using Next.js, TypeScript,
FastAPI, SQLAlchemy 2.x, Alembic and SQLite. The repository was empty when this
module was implemented, so the academic-year, faculty, student and evidence
foundations are included here. No existing application records were replaced.

## Run locally

Requirements: Python 3.12+, Node.js 20.9+ and npm. Run commands from the repository
root. The installed environment in this workspace is already migrated and seeded.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
npm ci
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m backend.seed
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in another:

```powershell
npm run dev
```

Open http://127.0.0.1:3000. The interactive API reference is at
http://127.0.0.1:8000/docs. For a production frontend, run `npm run build` followed
by `npm start`. Linux/macOS use `.venv/bin/python` for the Python commands.

On the implementation machine, the global `npm` shim points to a missing file.
Use `node 'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js'` in place of
`npm`, or repair the local Node installation. This does not affect the app.

Optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///<repo>/data/faculty.db` | SQLite database location |
| `EVIDENCE_ROOT` | `<repo>/storage/evidence` | Local evidence root |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Next.js API proxy destination; set before build/dev |

The app is intended for a trusted administrator on localhost. Authentication,
public hosting, multi-user concurrency and multi-department support are outside
this module. Keep both servers bound to loopback.

## Workflow

1. Open **Masters** and add faculty and students, including known name variants
   and ORCIDs. No fictitious people or sample papers are added to the live database.
2. Open **Add publication**, enter a DOI, and fetch metadata. This is a preview;
   lookup does not save anything. Retry or select **Enter manually** if lookup fails.
3. Review/edit bibliographic fields and the complete source author list. A full
   publication date is required for reporting. Missing or partial source dates
   are left blank rather than assuming a day/month.
4. Map authors to faculty, students, external or unknown. Confirm suggested
   matches. Select one faculty claimant, or mark the paper non-claimable.
5. Confirm indexing manually, attach evidence, check the review confirmation,
   and save. Evidence is queued before saving and uploaded after the record
   receives its ID. Failed uploads can be retried on the saved record.
6. Use the dashboard filters and clickable counts to open the underlying papers.
   Open a paper to edit metadata, mappings, claimant, date, evidence or activity.

## Data model and invariants

- `publications` stores one bibliographic record, raw metadata/provenance and
  institutionally confirmed KPI fields. DOI is normalized to lowercase without a
  resolver prefix. Its SQLite column has a case-insensitive unique constraint.
  A deactivated record still reserves its DOI and may be reactivated by editing.
- `publication_authors` stores ordered source details and optional internal
  identity. Faculty and student links have foreign keys and identity checks.
  Each internal person can appear once per paper. A partial unique index permits
  at most one claimant per publication; a check restricts claimants to identified
  internal faculty. API validation additionally requires exactly one claimant
  when a claimable paper has internal faculty.
- `faculty` and `students` are lightweight master directories. Deactivation
  retains historical links. Matching ignores inactive masters for new suggestions.
- `academic_years` stores non-overlapping 12-month date ranges. The seed adds
  July–June years 2024–25 through 2028–29 without modifying existing years.
  Additional years can use another start month through Masters. Publication dates
  must fit exactly one configured year. Editing a date reassigns its year.
- `evidence_files` stores file metadata and relative paths, not file contents.
- `change_logs` records publication creation, edits (including before/after author
  and claimant mappings), deactivation, and evidence additions/removals.

The initial Alembic migration is a frozen schema definition. Run `alembic upgrade
head` for upgrades, `alembic check` to check for schema drift. The seed is idempotent.
There are no stored monthly, quarterly or annual aggregate records.

## DOI integration and matching

DOI and BibTeX sources append to one compact import queue. The DOI input accepts
one identifier or a newline/comma/semicolon separated list; resolver URLs and
`doi:` prefixes share save-time normalization and duplicates appear once.
Metadata lookup is sequential, reports progress and never writes publications.
BibTeX supports one or several entries, with optional DOI enrichment.

The queue auto-selects a sole exactly matched Faculty claimant. Multiple matched
Faculty need a claimant selection in the row; weak/ambiguous suggestions require
exception editing. UNKNOWN co-authors are retained with non-blocking warnings.
There is no per-record approval step: use inline edits and **Add All Ready (N)**.
Each record saves independently; failures, duplicates and already saved rows stay
out of subsequent adds. **Edit** opens full author/bibliographic/evidence fields
and **Return to queue** retains changes and queued files without saving.

Indexing is multi-select and independent of institutional classification
(INTERNATIONAL, NATIONAL, OTHER, UNKNOWN). No classification is guessed from a
publisher. Impact factor remains nullable; quartile supports Q1–Q4, NOT_APPLICABLE
and UNKNOWN. Selected-row bulk actions apply only when explicitly requested;
adding an indexing tag preserves other meaningful tags. Classification and
indexing KPI drill-downs retain the applied reporting date range.

`PublicationMetadataProvider` is the provider interface; `CrossrefProvider` uses
the free [Crossref works API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).
It has a bounded HTTP timeout and returns actionable failures. DataCite can be
added behind the same interface; it is not implemented in this version.

Metadata includes source author order, personal/consortium names, ORCID,
affiliations, dates, title, venue, publisher, identifiers, URL, source timestamp
and the raw response. Missing fields stay optional in the preview.

Matching prioritizes exact faculty ORCID, normalized name, name variant, then
conservative fuzzy suggestions. Conflicting known ORCIDs reject a name match.
Ambiguous identical names and fuzzy results remain unmapped until confirmed.
Suggestions are advisory scores, not statistical probabilities. The final
review checkbox applies to both exact and manually confirmed mappings.

## Counting rules

The reporting service selects publications once, then computes counts and sets
of distinct internal person IDs. Joining multiple authors never multiplies the
department publication count. Each faculty row has separate **claimed** and
**authored** counts. Student metrics count each paper once and list distinct
faculty collaborators. Inactive papers are excluded unless explicitly included.

Indexing is a multi-select JSON list of validated categories. Scopus and Web of
Science are explicit categories; SCI/SCIE is a union so a paper tagged with both
counts once. No Web of Science membership is inferred from another category.
Student **indexed** counts include every category except NONE/UNKNOWN.

Monthly, quarterly and half-year periods are offsets from the configured year
start. In the default July–June year, 18 September 2026 is September, Q1, H1 and
AY 2026–27. All filter/drill-down paths share the same selection service and
drill-downs intersect the existing dashboard filters.

Unique-author cards count people, so their publication drill-down may have a
different row count. The page explains this distinction. Faculty-only and
student-only classifications refer to the composition of **internal** authors;
external collaboration is an additional independent label. Faculty + Student is
the mixed internal-author category; Student + Faculty additionally indicates a
mapped student marked as first author. Unknown authors are not treated as external.

## Evidence and Git workflow

Evidence is stored under
`storage/evidence/<year-start>-<year-end>/PAPER/<publication-id>/<uuid>.<extension>`.
The database keeps original filename, category, content type, size and SHA-256.
PDF, PNG, JPEG and DOCX are supported up to 25 MB each. View and download links
use publication-scoped API routes. DOCX downloads rather than rendering inline.
UUID paths and basename sanitization prevent filename traversal. Upload failures
remove partial files. Evidence can be removed and replaced from the UI.

`data/faculty.db` and evidence are intentionally **not ignored**. Only SQLite
transient `*.db-wal`, `*.db-shm`, `*.db-journal` files are ignored. Before switching
devices, stop the app, commit the database and evidence together, and pull the
latest repository on the other device before starting. SQLite is binary; avoid
divergent edits across devices. No database or publication data is sent to
Crossref; only the requested DOI is queried.

## Verification

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m backend.seed
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check
npm run typecheck
npm run build
npm run test:e2e
```

Backend tests use temporary SQLite databases created by the actual migration.
Browser tests start temporary API/database/evidence storage and a Next dev server
on ports 8011/3001. They use installed Microsoft Edge through Playwright. For
another browser, change `channel` in `playwright.config.ts` and install the
corresponding Playwright browser. Automated tests never seed example papers into
the live database. Live metadata availability is verified separately, not used
as a dependency of automated tests.

## Manual acceptance checks

1. Add Faculty A/B and Students X/Y in Masters.
2. Enter a DOI in URL form. Confirm it is normalized, all authors appear, and
   nothing is stored until you review and save. Repeat the DOI and open the
   existing-record link. Try a nonexistent DOI and continue manually.
3. Create P1 with A/B/X/external Y, claimant A, date 18 September 2026; then P2
   with B/X/Y, claimant B. Expected totals: 2 papers; A claimed/authored 1/1;
   B 1/2; X authored 2; Y authored 1; 2 papers with students; 2 unique faculty
   and 2 unique students. Multiple faculty must never inflate department totals.
4. Select September, Q1, H1 and AY 2026–27. Click each KPI count and compare the
   underlying publications. Test combined faculty, student and indexing filters.
5. Upload multiple evidence files. Open View and Download; remove a file and
   verify the detail count changes. Edit mappings, switch claimant, and move a
   publication date into the next academic year; confirm updated reports/history.
6. Mark a record non-claimable, then deactivate it. Verify it is excluded from
   normal reports, visible with Include inactive, and can be reactivated in Edit.

## Remaining limitations

- Crossref only; DOI records registered elsewhere may require manual entry.
- No indexing verification API or automatic ORCID identity proof.
- No authentication, approval workflow, public deployment, or concurrent admin editing.
- Department-scale reports load the selected records in memory; suitable for this
  small department, not a multi-department analytics warehouse.
- Evidence uploads follow record saving rather than forming one atomic transaction
  with the filesystem. The UI explicitly reports partial success and supports retry.
- A missing local evidence file returns a clear 404; synchronize the evidence
  directory along with the SQLite database when moving between devices.
- No-DOI duplicate detection is an exact normalized title/year/venue warning;
  uncertain records are never automatically merged.

## Books / Book Chapters Published

Open **Books / Chapters** for the department report, or **Add Book / Book Chapter**
for single or multiple DOI lookup in one compact queue, or manual entry. Paste newline/comma/semicolon-separated identifiers (spaces before recognizable DOI prefixes also work). Each item is independently reviewed and validated; use Add All Ready or Save Selected for partial saves. Crossref metadata fills an editable review form, detects book/chapter types and reuses Faculty/Student matching. Nothing is saved until reviewed. Select or review the work type first. Chapters require the parent book
title, page range and at least one author. ISBN is optional; ISBN-10 and ISBN-13
checksums are validated, with original formatting preserved and equivalent
ISBN-10/13 values normalized for matching. DOI normalization reuses the paper
module. Repeated DOI values are blocked even for inactive records; no-DOI title,
parent title, publication year and ISBN matches require explicit review before a
separate record is saved. Records with missing ISBN still receive duplicate checks.

Each work has ordered contributors with explicit AUTHOR or EDITOR roles. For a
chapter, EDITOR means parent-book editor. Faculty/Student Master links belong only
to the current department; other VCE departments and external institutions retain
names and affiliations without being added to department masters. Identity and
affiliation validation is shared with patents in `backend/affiliations.py`.
A person may be both author and editor, but cannot be added twice in the same
mapped role. Scope flags are derived from affiliation rather than edited separately.

New works require exactly one mapped current-department faculty claimant. Historical unclaimed works remain readable and editable. A single matched Faculty author is auto-selected after DOI lookup; multiple matches require a choice. UNKNOWN coauthors remain persisted and do not block save. Chapter
claimants must be chapter authors. A BOOK with a department editor can qualify
for the department total; a BOOK_CHAPTER requires a department chapter author.
Authored counts always require AUTHOR role. Claimed and authored totals are
separate, and all department counts use unique work IDs. The student table counts
unique authored works and lists mapped department faculty coauthors. Chapter
collaboration flags describe chapter authors, excluding parent-book editors.

Every report uses publication_date with inclusive From Date and To Date boundaries.
KPI cards and faculty/student count cells drill into records with the same filters;
detail links and Back to report retain the date range and current drill selection.
All work records includes unresolved and editor-only chapters outside department
report eligibility. Filters cover type, faculty, student participation, other VCE
departments, external collaboration, publisher, ISBN and inactive records. The main
research overview includes book/chapter totals and faculty claimed/authored counts.

Optional DOI metadata uses the existing Crossref provider and is preview-only.
Applying the reviewed preview asks before replacing matching fields and contributors;
manual entry does not depend on the provider. ISBN metadata retrieval is not implemented.

Migration `6844ca3e60d8` adds book_publications, book_contributors and book_change_logs,
and a nullable book_record_id owner on EvidenceFile. The evidence ownership CHECK
permits exactly one publication, patent or book owner. Claimant uniqueness is also
protected by a partial SQLite index. Existing publication and patent data/evidence
remain intact. Downgrade refuses to discard populated books tables.

Evidence categories: Cover Page, Title Page, Copyright Page, ISBN Page, Chapter
First Page, Table of Contents, Publisher Proof, Full Chapter and Other. Multiple
files reuse the shared upload/view/download/removal service, size/type validation,
generated filenames and SHA-256 tracking. Storage follows the existing convention:
`storage/evidence/<July–June folder>/BOOK|BOOK_CHAPTER/<record-id>/<generated-file>`.
Files are stored on disk, never as binary database content. If uploads partially
fail, the editor retains the saved record and pending files for retry.

Tests cover the B1 counting example, books and chapters, roles, affiliation/mapping,
claim limits, duplicate normalization/review, date boundaries, KPI drilldowns,
filters, evidence ownership and migration preservation. Browser tests exercise
entry, radio claimant selection, evidence, edit, clickable KPIs and date retention.
They use `.next-e2e` so an existing development server can remain running.

## Approved Faculty Master and journal claimant reconciliation

The user-approved 17-member roster and all 100 supplied spellings are kept in
`data/department_faculty.json`. Seed the Faculty Master explicitly with:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m backend.seed_faculty
```

The seed upserts by unique employee ID, preserving faculty IDs, existing ORCID,
Scopus identifiers and publication links. It sets the exact approved display
names/designations and active status. Other faculty records remain intact. It
never creates publications, students, patents or books. Repeated runs do not
create duplicate faculty or aliases. The general academic-year seed remains separate.

Faculty.name_variants remains the existing JSON list, deduplicated by normalized
name. Faculty.name_variant_strengths is a JSON map from normalized alias to
STRONG or WEAK, added by migration `e6d27aff4dcc`. Thus no duplicate alias table is
needed. All 100 approved spellings are covered by 48 normalized aliases. Three
normalized aliases are weak: M Asif, M Perumal and F Unnisa. The Masters editor
shows all aliases and an editable weak-alias list. Old API clients that omit
strength metadata preserve weak safeguards for retained aliases.

`normalize_person_name` lowercases, collapses whitespace, removes leading
Dr/Mr/Ms honorifics, handles punctuation and combines consecutive initials
(H.S., H S and HS). Display names are stored exactly. It never invents expanded
initials or spelling alternatives; compound-name formatting is covered by the
explicit approved variants. Matching prioritizes exact ORCID, canonical name,
strong approved alias and weak alias. Cross-person alias conflicts remain
ambiguous. Weak aliases and fuzzy suggestions never automatically assign authors.

Reconcile a historical journal workbook without importing it:

```powershell
.\.venv\Scripts\python.exe -m backend.reconcile_claimants 'F:\Downloads\Journals.xlsx' --reader-python 'C:\Users\silic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

The reader interpreter needs openpyxl; the bundled workspace runtime includes it.
Use `--sheet` if the workbook has more than one journal sheet and `--output` to
choose a report directory. The script treats Authors as the department claimant,
keeps every unique original value and original Excel row number, reports blanks
and unmatched values, and verifies that grouped row totals equal all nonempty
journal rows. It does not split a cell into a fabricated complete author list.
Reports are Markdown, CSV and JSON under `reports/journal-claimants` by default.
Only exact canonical/approved keys are used in reconciliation. An unmatched name
never creates a Faculty Master record or an inferred variant. No publications
are imported until the user reviews the claimant reconciliation and authorizes
an import separately.

### Approved historical claimant aliases

`data/historical_faculty_aliases.json` records the additional user-approved
STRONG aliases, including intentional historical misspellings. Apply them with:

```powershell
.\.venv\Scripts\python.exe -m backend.approve_historical_aliases
```

This update is additive and idempotent. It preserves all existing aliases,
canonical names, faculty IDs, active status, ORCID/Scopus IDs and activity links.
It requires the referenced Faculty Master records to exist and never creates
historical faculty automatically. Before writing, it checks every planned alias
against canonical names and aliases of all faculty, including inactive records;
conflicts stop the entire update. The base roster seed also preserves additional
approved variants on subsequent runs.

The 18 supplied historical spellings add 16 distinct normalized keys, bringing
Faculty Master variants to 64. The Journal reconciliation now retains all 35
previously matched rows and resolves exactly 102 additional rows. Of 138 rows,
137 match and one remains unresolved: Archana Chittari. Faculty Master remains
19 records; VCE1476 and VCE967 are retained with their existing statuses. No
publications are imported by either command.

## Pasted BibTeX and conference publications

Use **Publications → Add publication → BibTeX**, paste one or several entries,
and choose **Parse BibTeX**. This is a read-only preview. Each entry has its own
review form and save operation; malformed entries do not discard valid entries.
The backend uses pinned `bibtexparser` 2.0.1 and its robust block parser/name
middleware, with pylatexenc for display text. Original entries remain in
`raw_bibtex`; `source_type` identifies BibTeX, BibTeX plus DOI, DOI, manual, or
historical Excel provenance.

`@article` maps to Journal; `@inproceedings` and `@conference` map to Conference.
Other entry types require manual classification. Year/month values are retained
in the preview but never converted into invented publication days. Supply an
exact date when DOI metadata cannot provide one. Missing optional DOI, impact
factor and quartile remain null. No file upload is required.

DOI enrichment uses the existing Crossref service, checks duplicates before
fetching, fills missing fields, and exposes differences without replacing BibTeX
values. Institutional indexing, impact factor and quartile require confirmation.
Authors retain source order; unique canonical names, ORCIDs and approved strong
aliases map through the existing matching service. Weak/fuzzy suggestions require
confirmation. BibTeX never automatically chooses the claimant. Select exactly one
active internal faculty author, or explicitly mark a record non-claimable.

Journal and Conference remain one Publication model. Conferences add optional
name, proceedings title, start/end dates, location, organizer and ISBN. Existing
evidence storage supports conference papers, proceedings first pages,
certificates, conference programs and indexing proof. Publication reports share
From/To dates, claimant, author, type, quartile, indexing and student filters.
Journal/conference faculty claimed and authored counts drill down independently.

Migration `b85dc163ab92` adds nullable fields and provenance without recreating
the publication table. Make and verify a backup before migrating a populated DB:

```powershell
.\.venv\Scripts\python.exe scripts/backup_journal_database.py --prefix pre_bibtex_conference
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/verify_publication_migration.py data/backups/<backup-file>.db
```

The verification compares every original row/column against the backup and
checks SQLite integrity and foreign keys. A destructive downgrade is rejected
once conference or BibTeX fields contain data.

## Reporting date presets

The shared Date Range selector resolves Custom, This/Last Calendar Year,
This/Last Academic Year, and This/Last Month against the browser's current
application date. Academic years run July 1 through June 30. Existing quarter
and half-year shortcuts remain under Additional calendar ranges.

Selecting a preset immediately refreshes reports. Editing either date switches
to Custom; Apply dates validates and commits the custom range. The resolved
day-month-year range is shown beside the selector. Preset choices persist and
recalculate on report navigation or reload; custom dates remain explicit.

All reporting APIs still receive only inclusive from_date and to_date values.
The shared components/DateRange.tsx and lib/date-range.ts serve the research
overview, publication dashboard/list and faculty KPI drill-downs, patents, and
books/chapters. New reporting modules can reuse the same provider and component.

## Publications executive overview

The Publications page uses one `/publication-dashboard` request for department
totals, overlapping indexing categories, stored quartile and classification
distributions, distinct faculty claims/authorship, confirmed student involvement,
monthly trends, recent records, and data completeness. It uses inclusive
`publication_date` boundaries and the existing reusable date presets.

`backend/publication_reporting.py` supplies SQL aggregation and shared SQL
predicates for dashboard counts and `/publications` drill-downs. Authors and
evidence use EXISTS predicates; counts use distinct publication IDs. Dashboard
scope covers Journal and Conference records. Legacy Other publications remain
accessible through the existing registry API.

Filters and drill-down selections persist in URL parameters; individual record
links support returning to the selected report. Faculty numeric columns sort
and drill down; monthly counts clamp their bounds to the selected range.
Distinct claimant/student counts and unclassified author-record counts drill
down to their associated unique publications, so their units differ from list
row counts. Unclassified Vardhaman affiliations do not imply student identity.

Possible duplicates are omitted because no reliable persisted flag exists.
Missing publication dates cannot occur under the current required schema.
The redesign adds no migrations and does not update existing publication data
or alter DOI, BibTeX, manual entry, or claimant rules.

## Research Records dashboards

The approved Tremor Raw + Apache ECharts design is used by the production
Research, Publications, Patents and Books / Chapters overviews. The former
`/research/design-preview` route is removed. Additional dashboard shells at
`/fdp`, `/certifications`, `/proposals` and `/consultancy` display **Not configured**
until their backend modules exist. No business data or schema was changed for
this presentation rollout.

All dashboards reuse `components/DateRange.tsx` for inclusive dates and presets
(academic years run July 1 through June 30). Dashboard UI and the shared faculty
research modal live in `components/dashboard`; one lazy-loaded SVG ECharts
wrapper lives in `components/charts/EChart.tsx`. Tremor Raw source attribution
and license are included. Prefixed Tailwind utilities and scoped dashboard CSS
avoid resetting record-entry styles.

Research trend aggregation accepts `calendar_year` and `granularity` on
`/research/overview`, retaining zero months/quarters/calendar halves and deriving
years from actual activity. The global range constrains the trend buckets.
Publication filters only affect publication-specific analytics. Publication and
book counts use publication date; primary patent counts use any recorded lifecycle event date, while
lifecycle event charts and lists use each event's own date. Claims and authored/
inventor/eligible-editor participation are separate, with distinct records and
people counted by the existing backend services.

Existing `/publication-dashboard` reporting remains available. Read-only
`/patent-dashboard` and `/book-dashboard` return module aggregates and month
bounds. `/research/faculty/{id}?from_date=...&to_date=...` provides the on-demand
faculty profile, using confirmed Faculty Master mappings. Chart, KPI and table
drill-downs preserve date/filter context. Profiles link to existing record detail
pages, and do not duplicate editing functionality.

Books DOI entry now stores optional classification and provider provenance. International/National cards and classification charts use reviewed values; historical blank classification remains Unknown. Financial shells never fabricate
zero revenue or funding. See [the rollout report](reports/dashboard-rollout.md)
for routes, components, validation and remaining module limitations.

## Historical patents — CY 2026

Patents allow multiple mapped department Faculty inventor claimants (including historical Faculty). One patent remains one department record. Publications and Books retain their existing claimant rules. Patent totals and attribution count each record once when any filing/publication/grant event is in the inclusive range; Filed counts use only filing dates.

The controlled source is `data/historical_patents_2026.json`. Dry-run with `.\.venv\Scripts\python.exe -m scripts.import_historical_patents --report reports/patent-import/dry-run.json`; add `--apply` only for an authorized import. The script stops on ambiguous mappings or conflicting existing records and preserves unmatched department inventors. The completed import report is `reports/patent-import/completion.md`.

### Patent types

Patent entry and editing require exactly one of `UTILITY`, `DESIGN`, or `COPYRIGHT` (Utility, Design, Copyright). Copyright is never Other. Patent Type filters apply to the registry, Overview, its type breakdown and CSV export. Research Overview includes the same three-category breakdown; faculty detail rows retain the type. API validation rejects other values; SQLite constrains stored non-null types. Legacy unspecified types remain unclassified instead of being inferred. The nine historical CY2026 records remain seven Utility and two Design.
