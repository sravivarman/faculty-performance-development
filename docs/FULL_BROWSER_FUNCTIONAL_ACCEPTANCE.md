# Full Browser Functional Acceptance — Phase 3E

**Current recommendation: FAIL — full browser acceptance rerun required**

The functional suite uses the real Next.js interface and Playwright browser
actions. It does not use the production database or evidence storage.

## Test isolation evidence

`scripts/e2e_server.py` creates one fresh directory beneath
`.test-tmp-e2e`, resolves `test.db` and `evidence`, migrates and seeds it, and
starts the API in the same process. Before migration it rejects either path if
it equals `data/faculty.db` or `storage/evidence`, and rejects paths outside the
test-owned root. The Playwright configuration starts that API alongside a fresh
Next development server. Therefore destructive browser actions run only against
test-owned data and test-owned evidence files.

## Operation coverage matrix

| Area | Browser coverage | Status | Principal specs |
| --- | --- | --- | --- |
| Department, Faculty, Student, Academic Year Masters | Create/read/edit, transfer, duplicate/protected deletion | PARTIALLY COVERED | `masters.spec.ts` |
| Publications | Manual creation/edit, authors/claimant, DOI/BibTeX queues, evidence, quality applicability, lifecycle/deletion | COVERED | `publications.spec.ts`, `record-deletion-workflow.spec.ts` |
| Patents | Inventors, lifecycle dates, evidence, type, export, date drill-down | COVERED | `patents.spec.ts`, `patent-types.spec.ts` |
| Books / Chapters | Chapter/contributors, DOI queue, evidence, validation and date drill-down | COVERED | `books.spec.ts`, `book-doi-queue.spec.ts` |
| FDP / Training | Create, participant role, edit, evidence, deactivate/reactivate | COVERED | `development-funding-functional.spec.ts`, `fdp-certifications-kpi.spec.ts` |
| Certifications | Complete/in-progress creation/edit, Faculty association, evidence | PARTIALLY COVERED | `development-funding-functional.spec.ts`, `fdp-certifications-kpi.spec.ts` |
| Funding | Sponsored-research creation, investigator, financial value, evidence, deactivate/reactivate | PARTIALLY COVERED | `development-funding-functional.spec.ts`, `dashboard-rollout.spec.ts` |
| Reporting periods and dashboards | Presets, custom range, KPI/drill-down, responsive layout | COVERED | `date-range.spec.ts`, `overview.spec.ts`, `dashboard-*.spec.ts` |
| Institutional scopes | Institution/Department/Faculty, current/activity-date attribution | COVERED | `institutional-reporting-acceptance.spec.ts`, `faculty-research-details.spec.ts` |
| Faculty Research Details | Profile, Department context, historical notice, record links | COVERED | `faculty-research-details.spec.ts`, `dashboard-rollout.spec.ts` |
| Publication Report Builder | Scope controls, field applicability, table/citation configuration | PARTIALLY COVERED | `publication-report-builder.spec.ts`, `institutional-reporting-acceptance.spec.ts` |
| Header/navigation | Desktop parents, routes, active/open behavior | COVERED | `portal-header.spec.ts` |

`PARTIALLY COVERED` means the supported workflow has browser coverage but not
every possible category, lifecycle variation, negative input, or export format.
It does not mean a feature is untested at the backend level.

## New Phase 3E functional workflows

`development-funding-functional.spec.ts` adds real-browser workflows for:

1. FDP create → participant selection → evidence upload → edit → deactivate →
   reactivate.
2. Certification complete create → evidence upload → change to in-progress →
   confirm evidence persistence.
3. Sponsored Research create → Faculty Master investigator selection →
   sanction amount → evidence upload → deactivate → reactivate.

All three create prerequisites through the isolated test API, but perform the
records under acceptance through visible browser controls. Evidence files are
in-memory PDFs supplied through Playwright and therefore remain test-owned.

## Execution commands

```powershell
# Full functional browser suite (all existing and Phase 3E browser specs)
npm run test:functional

# Cross-module smoke suite
npm run test:functional:smoke

# New workflows only
npm run test:e2e -- tests/browser/development-funding-functional.spec.ts

# HTML report after a run
npx playwright show-report
```

Playwright retains failure screenshots and traces according to
`playwright.config.ts`.

## Actual execution evidence

- Prior Phase 3B local backend evidence: 14 focused institutional tests passed.
- Prior browser evidence: the Faculty Research Details acceptance test passed;
  two dashboard locator/label regressions were corrected afterward.
- Phase 3E source additions were statically verified with TypeScript and diff
  checks. The full browser execution remains pending locally because this agent
  environment terminates long Playwright commands after roughly 30 seconds.

No unexecuted suite is represented as passed in this record.

## Phase 3E.1 failure triage and repairs

The first Phase 3E full run reported 43 tests with 27 passing and 16 failing.
The affected controls were compared with the rendered component source before
changing either assertions or application behavior. The repaired failures are
listed below; a full local rerun remains required to replace this triage record
with completed browser evidence.

| Original failure area | Classification | Verified cause and repair |
| --- | --- | --- |
| Book / Chapter manual contributor workflow | STALE_TEST | `BookEditor` now derives institutional affiliation from Faculty or Student Master selection. Tests now choose the current `Person Type`, Faculty/Student selector, or External organization control rather than removed Affiliation and local-reference dropdowns. |
| Book DOI exception review | STALE_TEST | The queue review uses the same standardized contributor card. The test now selects its created Faculty Master record through the searchable selector and retains its claimant assertion. |
| Patent and Copyright inventor workflows | STALE_TEST | `PatentEditor` uses the standardized Person Type and Faculty/Student/External controls. Tests no longer address removed Affiliation or local-reference fields and continue to assert claimant, lifecycle, evidence, type, and export behavior. |
| Reporting-period tests on Books, Patents, dashboards, and the shared date component | STALE_TEST | `DateRange` renders From Date and To Date only for `Reporting Period = Custom`. Tests select `Custom`, check that the date controls appear, apply the range with `Apply range`, and validate preset values through the inclusive range caption. |
| Institutional header branding | STALE_TEST | The header intentionally shows `Faculty Research & Development Portal` without the former EEE-only suffix. The header test now verifies the institutional title and absence of the retired suffix while retaining navigation assertions. |
| Certification in-progress assertion | LOCATOR_ERROR | `In Progress` occurs in both the status eyebrow and the detail value. The test now scopes the assertion to the Status row in the persisted detail grid. |
| Research-dashboard chart count | STALE_TEST | Five chart-ready visualizations are intentional: Research Activity Trend, Patents by Type, and the three publication analytics distributions. The test verifies those named sections rather than an unexplained legacy count of four. |
| FDP KPI selection | STALE_TEST | The first FDP card is intentionally `Faculty Participated`, replacing the earlier `Distinct Activities` card. The KPI test now expects the documented distinct-Faculty metric while continuing to check that a KPI selection never refetches or replaces its summary. |
| Publication dashboard count after save | FIXTURE_ERROR | The assertion depended on the browser's persisted/default reporting period. Its fixture now opens an explicit September 2026 inclusive range containing the record, while retaining the dashboard, drill-down, edit, and evidence assertions. |
| Sponsored Research save heading in the full run | TIMING/ISOLATION INVESTIGATION | The focused browser workflow previously passed. Its save and persisted-heading assertions are retained; no product change was justified without a reproducible failed save response or validation error. Rerun it independently and within the full suite to detect any remaining order-dependent behavior. |
| Overview, Research Overview, and KPI record drill-downs | VERIFIED CONTRACT | Their fixtures use explicit periods and API-created records. The test source was checked against the current distinct-record, active-record, and Department-attribution contracts; no unsupported expected values were changed. |

### Isolation safeguards

`scripts/e2e_server.py` still creates a unique, migrated SQLite database and
evidence directory below `.test-tmp-e2e` for every Playwright invocation. It
resolves and rejects production database/evidence locations before migration,
and fails if either test path escapes the test-owned root. The repaired tests
also create their own Faculty/Student prerequisites where the workflow needs
them, avoiding reliance on production Master data or prior browser state.

### Verification following repair

- `npm run typecheck` — passed.
- `git diff --check` — passed.
- `npx playwright test --list tests/browser` — passed; 43 tests discovered.
- Focused and full Playwright executions initiated in this agent environment
  were terminated during web-server startup at the environment's 30-second
  execution limit, before test outcomes were emitted. They are therefore
  **not** recorded as passed.

Run these commands locally to complete the acceptance evidence:

```powershell
npm run test:e2e -- tests/browser/books.spec.ts tests/browser/book-doi-queue.spec.ts
npm run test:e2e -- tests/browser/patents.spec.ts tests/browser/patent-types.spec.ts
npm run test:e2e -- tests/browser/date-range.spec.ts tests/browser/portal-header.spec.ts tests/browser/dashboard-design.spec.ts
npm run test:e2e -- tests/browser/fdp-certifications-kpi.spec.ts tests/browser/development-funding-functional.spec.ts
npm run test:functional:smoke
npm run test:functional
```

## Known limitations and follow-up coverage

1. Run `npm run test:functional` locally. Promote the recommendation only when
   the complete suite passes, including the critical create/edit/evidence and
   reporting-period workflows.
2. Add equivalent browser creation flows for Consultancy and Internal Grants if
   their category-specific forms gain behavior beyond the shared FundingEditor.
3. Add browser assertions for Certification deactivate/reactivate only if that
   lifecycle action is exposed in the user interface; the current detail page
   supports edit and evidence but has no dedicated lifecycle control.
4. Download-byte validation and external DOI-provider calls remain backend or
   optional integration concerns; deterministic queue workflows are already
   browser-covered without external-network dependence.
