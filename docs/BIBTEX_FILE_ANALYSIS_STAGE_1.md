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
