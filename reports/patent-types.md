# Patent type update

Supported values are exactly `UTILITY`, `DESIGN`, and `COPYRIGHT`, displayed as Utility, Design, and Copyright. Copyright is never classified as Other.

The shared Add/Edit form requires a type selection. The registry and Patents Overview have a Patent Type filter. Overview and Research Overview show all three categories, including zero-count Copyright. Patent detail, list and Faculty Research Details rows display the type. CSV exports include the canonical type and display label and respect the same filters/date range as the displayed records.

API creation/editing requires one of the three canonical values; unsupported values and filters are rejected. Historical import accepts the three labels and normalizes them to canonical values. Future Copyright import was verified in an isolated test database.

Migration `a03d26e71002` adds a SQLite type check and preserves the existing lifecycle status check, identifiers, dates, inventors and multiple claims. Legacy unspecified types remain null rather than being inferred; new/edited API records require an allowed value. Unsupported existing non-null types stop migration for manual classification.

The database backup is `data/backups/pre_patent_types_20261003_004224.db`. Every pre-existing table row was compared before/after migration and again after the final live smoke check. All values are unchanged. The nine historical records remain **7 Utility, 2 Design, 0 Copyright**. The import dry run still identifies all nine as existing with zero ambiguity. Details: `patent-type-audit.json` and `patent-import/type-verification-dry-run.json`.

Validation:

- Full backend suite: **279 passed**.
- Frontend unit suite: **49 passed**.
- Six relevant browser cases passed across focused runs: two patent lifecycle/form checks, three shared dashboard/modal checks and one complete Copyright workflow. Test expectations were updated for the additional chart and new type selector.
- Coverage includes Utility/Design/Copyright creation and editing, unsupported types, filtering, three-category breakdowns, CSV labels/filtering, faculty detail types, historical import idempotency and migration preservation of records/claims.
- Production build, TypeScript type-check and backend Python compile check passed.
- Read-only live browser/API checks confirm Utility 7, Design 2, Copyright 0 in both overviews, a zero-result Copyright filter and the exact API enum. No Copyright record was added to the live historical data.

View: http://127.0.0.1:3000/patents?from_date=2026-01-01&to_date=2026-12-31
