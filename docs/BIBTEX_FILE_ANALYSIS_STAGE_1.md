# BibTeX file analysis — Stage 1 architecture

The existing `BibTeXPublicationParser` is the single parser for pasted and
uploaded BibTeX. It already preserves source order, citation keys, raw entries,
author order, malformed-block diagnostics, DOI normalization, and conservative
Faculty/Student match suggestions. The existing publication save path remains
separate and is not called by file analysis.

`POST /publications/analyze-bibtex-file` reads one UTF-8 `.bib` upload and an
optional UTF-8 Scopus `.csv` upload into request memory. It enforces the BibTeX
5 MB default and the CSV 10 MB default, calls the established parser with DOI
enrichment disabled, checks existing publications through read-only SQLAlchemy
queries, and returns a review payload. Uploaded bytes are closed and discarded
after the response; there is no analysis table, evidence file, database write,
or server-side cache.

The client retains the returned analysis only in component state and renders a
25-row review page at a time. It offers search, disposition filters, sorting,
details, and clear/replacement controls. It has no save, claim, or import
action. Stage 2 can reuse the returned parsed drafts after explicit per-entry
review and claimant selection, but must make a new validated save request for
each approved record.

Primary dispositions are mutually exclusive: parse error, unsupported type,
exact database match, exact within-file duplicate, possible duplicate, metadata
review, or new candidate. Exact DOI and normalized title/year/venue matches are
confirmed; high-similarity title/year/venue matches are possible only and never
saved automatically. Inactive publications participate in database matching.

## Stage 1B Scopus reconciliation and dates

### Stage 1B.2 source identity and metadata comparison

Scopus reconciliation is analysis-only and now reports two independent
dimensions. `MATCHED`, `AMBIGUOUS`, `BIBTEX_ONLY`, `CSV_ONLY`, and
`IDENTITY_CONFLICT` answer whether the uploaded source records identify the
same work. `CONSISTENT`, `INFORMATIONAL_DIFFERENCES`, `REQUIRES_REVIEW`, and
`IDENTITY_CONFLICT` describe their metadata comparison. A compatible author
formatting difference, supplementary source field, or document-type mapping
never changes a matched publication into an identity conflict.

Author comparison is deliberately conservative: Unicode, punctuation,
surname-first formatting, and full-given-name versus matching initials are
accepted only when surname and all available initials agree. Changed author
order, author counts, or uncertain names remain reviewable; source names and
order are never rewritten.

For conference candidates, proceedings title, conference name, event date,
location, publisher, identifiers, and volume are retained as separate
transient comparison data. A Scopus BibTeX `journal` field can be a proceedings
title for a conference paper. Conference event dates are never treated as
publication dates. No comparison result writes a publication, author,
claimant, evidence item, or master record.

### Stage 1D import-readiness assessment

Each analyzed entry also has a transient import-readiness plan. It is derived
from the same prerequisites used by the existing single-publication save path:
supported Journal/Conference classification, complete date, required metadata,
contributor certainty, and one subsequently selected Faculty claimant. It
reports an overall status plus independent blockers, explanations, contributor
counts, and eligible Faculty claimant candidates. `READY_FOR_REVIEW` only
means that a later human review may consider the record; it never enables an
import action in this analysis workflow.

The response has two explicit readiness scopes. `all_records` counts every
uploaded BibTeX entry and is retained for auditing duplicate restrictions.
`potentially_new` counts only records with `NO_DUPLICATE_DETECTED`; it is the
scope used by the Import Readiness cards. Its blockers overlap: a record may,
for example, require both an exact date and a claimant. The card definitions
are therefore: **Potentially new** = no duplicate detected; **Ready for human
review** = no blocker in that candidate scope; **Missing exact dates** = a
candidate with `DATE_VERIFICATION_REQUIRED`; **Classification**, **Contributor**,
and **Claimant** review = candidates carrying those named blockers; and
**Special / unsupported** = candidates blocked by special-record policy or an
unsupported module. Source-wide metadata totals remain in the separate
Metadata quality section and must not be compared as if they used the same
denominator.

Candidate claimant rows include the existing Faculty Master ID, match evidence,
and current Department when recorded. They do not infer a Department at the
publication date: an unknown or baseline historical affiliation remains
explicitly uncertain until a later reviewer has an exact date and uses the
existing attribution rules. Existing database duplicate references likewise
show their current claimant read-only when one exists.

DOI date evidence is retained in browser state by normalized DOI and applied
to all source entries with that DOI, rather than by citation key. Day-precision
verification may clear the session-only date blocker; month/year evidence
remains incomplete. Users can request consecutive bounded batches of
previously unverified DOIs, while explicit per-entry retry remains available.

The optional CSV is transient source metadata, not an import. It requires
`EID`, `Title`, `Year`, and `Document Type`; optional Scopus columns are kept
as text and formula-like values are never executed. Reconciliation first uses a
normalized DOI, then an exact normalized title-plus-year fallback. Multiple
matches are marked `AMBIGUOUS`, document-type disagreements are `CONFLICT`, and
unmatched sides remain `CSV_ONLY` or `BIBTEX_ONLY` for manual review.

Every BibTeX row also has independent duplicate, metadata-readiness, document
classification, publication-date, and Stage 2 eligibility signals. None of
those dimensions overwrites either source or changes any publication record.

`POST /publications/analyze-bibtex-file/enrich-dates` is a separate, explicit,
bounded reviewer action (maximum 25 DOI requests). It uses the existing
Crossref provider only when requested and returns online, published, print, and
issued candidates with the exact precision supplied by Crossref. It never
creates a date, record, queue item, or database write.

## Stage 1B.1 diagnostics

Reconciliation reports CSV-record and BibTeX-entry totals separately. For CSV,
`unique_csv_matches + ambiguous_csv_records + csv_only_records = total_csv_records`.
For BibTeX, `unique_bibtex_matches + ambiguous_bibtex_entries + bibtex_only_entries
= total_bibtex_entries`. These source-specific totals must not be added together:
they describe different sides of the same comparison.

An ambiguous CSV row is attached to every candidate BibTeX entry with its source
row, EID, match method, candidate entry numbers, and ambiguity reason. This
prevents a candidate from being incorrectly labelled `BIBTEX_ONLY` simply
because no one-to-one decision was made.

Field-level source differences retain the original values and are classified as
`INFORMATIONAL`, `REQUIRES_REVIEW`, or `IDENTITY_CONFLICT`. Field counters can
overlap because one entry can differ in more than one field. The UI presents
both the number of distinct entries with differences and the per-field counts.

Date enrichment returns the provider, date type, precision, and whether the
preferred value is an exact online date. Online day-precision dates are
preferred; print, published, and issued alternatives remain visible. A title or
year discrepancy between the uploaded row and Crossref marks the result
`IDENTITY_CONFLICT`; a disagreement with an existing BibTeX date is separately
flagged. No suggestion is ever applied automatically.

## Stage 1C publication-date verification

The explicit **Verify Publication Dates Automatically** action remains limited
to 25 unique DOI values and runs sequentially. It first queries the existing
Crossref provider. If Crossref lacks an exact online date, it may query
DataCite, OpenAlex, and the DOI-resolved publisher landing page. All work is
request-scoped and discarded after the response.

The verifier preserves every date candidate with source, source URL, source
field, retrieval time, type, precision, and assessment. `created` and
`deposited` Crossref fields are deliberately ignored as DOI lifecycle metadata,
not publication dates. Dates are selected only in this order: exact online,
exact publication, exact print, partial month/year, then unresolved. It never
creates a day or month from partial source data and never uses a conference
event date as a publication date.

Identity is evaluated conservatively from the uploaded title and returned
provider titles: `VERIFIED_IDENTITY`, `LIKELY_IDENTITY`, `IDENTITY_CONFLICT`,
or `INSUFFICIENT_EVIDENCE`. A material title conflict prevents a suggested
date. Different exact candidates are reported as `CONFLICTING_DATES` instead
of being silently ranked by apparent authority.

Publisher retrieval accepts HTTPS only, validates DNS targets as public,
revalidates every redirect, limits redirects and response size, requires HTML,
does not execute JavaScript, and reads only deterministic structured metadata
(citation, Dublin Core, Highwire, and JSON-LD fields). It does not crawl PDFs,
evade access controls, or bypass publisher restrictions.

## Stage 2A review preparation workspace

The **Bulk Publication Review Workspace** is opened explicitly from a completed
BibTeX/Scopus analysis. It is a browser-only preparation layer, not an import
queue: it never calls a publication-create, update, claimant, evidence, or
Master-data endpoint. The existing `PublicationImportQueue` is deliberately
not used by this workspace.

Each session is identified by a random session ID plus SHA-256 fingerprints of
the original BibTeX file and, when supplied, the Scopus CSV. A record identity
combines that source fingerprint, source entry position, normalized source DOI,
and verified Scopus EID. Citation keys are never used as identifiers because
they can repeat. Source files themselves are not copied into a session.

Progress is held only in the browser and is also available through an explicit
**Export Review Session** JSON package. Packages contain a schema/version,
timestamps, source fingerprints, original and proposed metadata, contributor
decisions, claimant selection, DOI evidence, review confirmations, warnings,
and an SHA-256 integrity digest. Restoration checks JSON safety, schema and
version, digest, unique record IDs, both source fingerprints, and a practical
file-size limit before accepting a package. Browser-local progress can be
deleted explicitly and is not described as a backup.

The digest is calculated from one shared JSON-compatible canonical form: object
keys are sorted recursively; undefined object members are omitted exactly as
`JSON.stringify` omits them; undefined array items become `null`; arrays retain
their order; and non-finite values are normalized to `null`. This prevents a
freshly exported JSON package from changing its protected representation merely
because JSON parsing removes optional undefined fields. The integrity envelope
is excluded from its own digest. SHA-256 detects accidental or deliberate
package modification; it is not reviewer authentication.

Restore validation is atomic. The current in-memory/browser-local review is
not changed unless the full package validates first. User-visible rejection
codes distinguish `PACKAGE_INTEGRITY_FAILED`,
`UNSUPPORTED_SCHEMA_VERSION`, `INVALID_PACKAGE_STRUCTURE`,
`SOURCE_FINGERPRINT_MISMATCH`, `DUPLICATE_RECORD_IDENTIFIER`,
`RECORD_IDENTITY_MISMATCH`, `PACKAGE_TOO_LARGE`, and unexpected
`RESTORE_FAILED` errors. File names are not part of source binding: identical
BibTeX and Scopus bytes remain compatible after a harmless rename, while changed
source bytes are rejected. Restored duplicate and Master-data findings remain a
historical snapshot that a future Stage 2B must revalidate.

Only records with no detected duplicate and a Journal or Conference proposal
can be selected for the Stage 2B preparation flow. Existing database matches,
possible/upload duplicates, ambiguous identities, Books/Chapters, and special
or unsupported records remain visible but cannot become preparation
candidates. Selective DOI verification reuses the Stage 1C endpoint and is
deduplicated by DOI with a clearly labelled maximum of 25 unique DOI lookups
per action. It remains explicit; the workspace never verifies the whole upload
automatically.

Reviewers may change a proposed draft, choose each author as Faculty, Student,
External, or Unresolved, and select exactly one claimant from confirmed Faculty
authors. A manual date proposal retains its evidence source, type, and any
explanation in the review package. All review confirmations are invalidated by
the relevant draft/contributor/claimant/date changes. `VALIDATED_FOR_STAGE_2B`
means only that the current package passed browser-side preparation checks; a
future Stage 2B must independently revalidate duplicate state, person IDs,
claimant eligibility, required fields, source identity, dates, and current
database state before it can save anything.
