# Institutional Reporting Acceptance — Phase 3C

**Recommendation: PASS WITH DOCUMENTED LIMITATIONS**

This is an acceptance and stabilisation record for the institutional reporting
work completed through Phases 1–3B. It does not approve a PostgreSQL migration,
centralised evidence storage, authentication, or deployment.

## Scope and architecture

| Area | API / service | Scope and date basis | Counting unit |
| --- | --- | --- | --- |
| Institution overview | `GET /research/overview`, `GET /research/scoped-overview` / `scoped_reporting.py` | Institution, Department, or Faculty; module-specific | Distinct parent record |
| Department filtering | Module list/dashboard APIs / `department_filtering.py` | `CURRENT` or `AT_ACTIVITY_DATE` | Distinct parent ID before pagination/counting |
| Faculty profile | `GET /research/faculty/{id}` / `dashboard_reporting.py` | Complete profile, or selected-Faculty Department context | One parent record per selected Faculty association |
| Publications report builder | `/publication-reports/*` / `publication_reports.py` | Institution, Department, Faculty claiming/contributing | Publication-wise or claimant Faculty-wise row |
| Faculty/Department identity | `/masters`, `/faculty`, `/departments` / `department_attribution.py` | Current or verified effective-dated affiliation | Stable Faculty and Department IDs |

The application has no reporting path that depends on an EEE name prefix or
hard-coded EEE Faculty IDs. EEE remains a valid historical Department record.

## Attribution and reporting-date rules

| Module | Reporting period rule | Department activity-date rule |
| --- | --- | --- |
| Publications | `publication_date` | `publication_date` |
| Patents | Any filing/publication/grant lifecycle event may qualify a period | `filing_date` |
| Books / Chapters | `publication_date` | `publication_date` |
| FDP / Training | `start_date` | `start_date` |
| Certifications | Completed: `completion_date`; active in-progress is current work | `completion_date`; undated in-progress work is not historically attributed |
| Funding | `sanction_date`, then proposal submission date, then start date | `sanction_date` only |

All date ranges are inclusive. `AT_ACTIVITY_DATE` never uses current Department
as a substitute for an unknown historical affiliation. A migration-baseline
affiliation without an effective start remains explicitly unverified.

## Module acceptance matrix

| Module | Institution / Department status | Faculty detail status | Safeguards and existing regression coverage |
| --- | --- | --- | --- |
| Publications | Supported through shared predicate | Claiming and contributed counts stay separate | `test_publications.py`, `test_department_filtering.py`, `test_publication_reports.py` |
| Patents | Supported through inventor links | Linked inventor records, lifecycle-aware period list | `test_patents.py`, `test_cross_department_associations.py` |
| Books / Chapters | Supported through contributors | One work per parent ID, contributor roles retained | `test_books.py`, `test_cross_department_associations.py` |
| FDP / Training | Supported through participants | Selected Faculty roles only; one activity row | `test_fdp_certifications.py`, `test_faculty_research_details.py` |
| Certifications | Completion/current-work semantics retained | Completed and in-progress remain separate | `test_fdp_certifications.py`, `test_faculty_research_details.py` |
| Sponsored Research | Supported through Faculty investigators | Project amounts are associated values, never personal allocations | `test_funding_projects.py`, `test_department_filtering.py` |
| Consultancy | Same funding association model | Contract and received values remain distinct | `test_funding_projects.py` |
| Internal Grants | Same funding association model | Beneficiary/investigator relationships retained | `test_funding_projects.py` |

## Reconciliation findings

- Institution totals are calculated from distinct parent records and must not
  be reconstructed by adding Department totals.
- A shared parent record may be credited once to each eligible Department, but
  is not duplicated within a Department.
- Faculty Department attribution uses the selected Faculty's own contributor
  association plus that Faculty's verified affiliation. A CSE coauthor does
  not credit an EEE Faculty member to CSE.
- Funding sums operate over selected project records, not contributor rows and
  not `SUM(DISTINCT amount)`. Identical sanctioned amounts on different
  projects remain independently included.
- Faculty profile funding values are labelled as associated project values;
  they are not allocations to a person or Department.
- Report Builder preview, Excel, and citation exports share report selection.
  Excel is the custom-table export; Word/PDF remain citation exports.

## Faculty Research Details

The existing modal remains the single Faculty-detail experience. It exposes a
complete institutional Faculty profile by default and a Department-attributed
context on demand. The identity header uses Faculty Master ID, employee ID,
current Department where recorded, designation, and inactive/historical state.
It retains links to existing record details and displays participant or
investigator roles without changing their underlying associations.

## Data integrity and performance observations

- The reporting services are read-only and do not update contributors,
  affiliations, templates, financial values, or evidence.
- Department filtering composes correlated `EXISTS`/parent-ID SQL predicates
  before module counts and pagination, avoiding association-row multiplication.
- Scoped overview preloads Faculty affiliations before resolution. The Faculty
  profile uses SQL predicates for each selected module rather than loading all
  Faculty profiles into the browser.
- SQLite validation does not establish PostgreSQL query plans. The planned
  PostgreSQL phase should measure representative dashboards and reports before
  adding indexes.

## Tests and evidence

Existing local evidence supplied during Phase 3B:

- `tests/test_faculty_research_details.py`, institutional reconciliation,
  Department filtering, and cross-department associations: **14 passed** in
  20.77 seconds.
- Initial Faculty Research Details / dashboard browser batch: the new Faculty
  details test passed. Two legacy dashboard-selector regressions were fixed;
  the final browser rerun is still required after the last label correction.

Phase 3C adds `tests/test_institutional_reporting_acceptance.py` for shared
parent-record reconciliation, selected-Faculty intersection, inactive Faculty
reportability, and distinct-project funding sums. It also adds
`tests/browser/institutional-reporting-acceptance.spec.ts` for the institutional
overview and Report Builder scope controls. The backend acceptance file collects
two tests successfully; full local execution is pending at the time of this
record, so no pass count is inferred here.

Run the final backend acceptance batch with:

```powershell
$testDir = ".test-tmp-phase3c-$([guid]::NewGuid().ToString('N'))"

.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $testDir `
  tests\test_institutional_reporting_acceptance.py `
  tests\test_institutional_reconciliation.py `
  tests\test_faculty_research_details.py `
  tests\test_publication_reports.py `
  tests\test_department_filtering.py `
  tests\test_cross_department_associations.py `
  tests\test_publications.py `
  tests\test_patents.py `
  tests\test_books.py `
  tests\test_fdp_certifications.py `
  tests\test_funding_projects.py
```

Then run:

```powershell
npm run typecheck
npm run test:e2e -- tests/browser/dashboard-rollout.spec.ts tests/browser/faculty-research-details.spec.ts tests/browser/institutional-reporting-acceptance.spec.ts tests/browser/publication-report-builder.spec.ts
```

## Remaining limitations and policy decisions

1. The final browser rerun and the full Phase 3C acceptance batch are required
   before changing this recommendation to `PASS`.
2. Certification in-progress records are intentionally visible as current work
   but cannot receive activity-date Department attribution without a verified
   completion date.
3. Funding period fallbacks and funding historical attribution intentionally
   use different date policies; this is documented behavior, not a conversion
   of proposal dates into sanctions.
4. There is no Faculty-level financial allocation model. Associated project
   values must not be summed across Faculty profiles.
