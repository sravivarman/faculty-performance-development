# Full Browser Functional Acceptance — Phase 3E

**Current recommendation: PASS WITH LIMITATIONS**

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

## Known limitations and follow-up coverage

1. Run `npm run test:functional` locally before promoting the recommendation to
   `PASS`.
2. Add equivalent browser creation flows for Consultancy and Internal Grants if
   their category-specific forms gain behavior beyond the shared FundingEditor.
3. Add browser assertions for Certification deactivate/reactivate only if that
   lifecycle action is exposed in the user interface; the current detail page
   supports edit and evidence but has no dedicated lifecycle control.
4. Download-byte validation and external DOI-provider calls remain backend or
   optional integration concerns; deterministic queue workflows are already
   browser-covered without external-network dependence.
