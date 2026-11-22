# Research, Consultancy and Internal Grant Implementation Audit

**Audit date:** 22 November 2026  
**Scope:** Research Proposals, Sponsored Research, Consultancy, and Seed Money / Internal Grants  
**Method:** Read-only source and test inspection of the current checkout. No application code, migrations, records, evidence, or navigation were changed.

## 1. Executive finding

The application has a substantial, shared **Funding Project** foundation for Sponsored Research, Consultancy, and Internal Grants. It supports CRUD, linked and manual investigators, category-specific high-level financial values, shared evidence, status-based financial totals, pagination, Faculty/Department reporting, and NBA funding-report previews.

It does **not** currently implement Research Proposals as a lifecycle module. `/proposals` is an explicit unconfigured placeholder, while `/research-projects/new` creates the shared `FundingProject` record directly. Consequently, the system cannot retain a proposal as a first-class record and later link or convert it to a sanctioned sponsored project without losing the intended lifecycle distinction.

This is an audit, not a statement that every existing tested feature has been re-executed in this session. The attempted focused test run could not start because the local virtual-environment Python launcher cannot resolve its configured Python 3.14 interpreter. Existing test coverage is catalogued below, but no new test result is claimed.

## 2. Evidence classification

| Classification | Meaning in this audit |
|---|---|
| Confirmed implemented | Present in the current source and reachable through the identified route/API. |
| Confirmed missing | No model, API, route, component, or service exists for the requirement. |
| Partially implemented | A general field or workflow exists but does not provide the required structured behavior. |
| Existing test coverage | A focused test file contains coverage; it was not necessarily run in this audit. |
| Requires browser or policy verification | Source inspection cannot establish user interaction, institutional policy, or access-control effectiveness. |

## 3. Current architecture inventory

### 3.1 Shared funding-domain foundation

| Layer | Confirmed implementation |
|---|---|
| Primary record | `backend.models.FundingProject`, table `funding_projects`; category is `SPONSORED_RESEARCH`, `CONSULTANCY`, or `INTERNAL_GRANT`. |
| Investigator association | `FundingProjectFaculty` supports Faculty Master links and manual external investigators, role, display order, optional agency designation, and designated-lead flag. |
| Active roles | UI offers `LEAD_PI`, `MEMBER_PI`, `CO_PI`, `ADMIN_PI`, and `BENEFICIARY`. Historical `PI` and `CO_INVESTIGATOR` remain readable for compatibility but cannot be newly selected. |
| API | `backend/funding_api.py`: options, create, paginated list, detail, update, soft deactivate, reactivate, and dashboard endpoints. |
| Pages/components | `FundingOverview.tsx`, `FundingEditor.tsx`, generic funding detail/edit routes, and shared evidence manager. |
| Audit history | `FundingProjectChangeLog` records an update action with title and status; it is not a complete field- or association-level history. |
| Evidence | Shared `EvidenceFile` ownership through `funding_project_id`; upload/list/download/remove endpoints. |
| Department scope | Current or activity-date Department attribution is available for list/dashboard calls. |
| Migrations | `c4d1e8a7b9f2` created the shared foundation; `d9e6f1a4c782`, `e2b7c4d9a613`, `f14e9c2a7b35`, and `a4c8f7e2d6b1` add manual investigators, role compatibility, and financial fields. |

### 3.2 Routes and navigation

| Business area | Overview | Create | Detail/edit | Navigation status |
|---|---|---|---|---|
| Research Proposals | `/proposals` | None | None | **Placeholder only**; absent from the Research Funding menu. |
| Sponsored Research | `/research-projects` | `/research-projects/new` | `/funding-projects/[id]`, `/funding-projects/[id]/edit` | Reachable as **Sponsored Research**. |
| Consultancy | `/consultancy` | `/consultancy/new` | Shared generic routes | Reachable. |
| Seed Money / Internal Grants | `/seed-money` | `/seed-money/new` | Shared generic routes | Reachable. |

`components/AppHeader.tsx` lists exactly Sponsored Research, Consultancy, and Seed Money / Internal Grants beneath Research Funding. It does not expose a Proposals link. `app/proposals/page.tsx` renders `UnconfiguredDashboard` for the `proposals` module.

### 3.3 API and service mapping

| Module | Endpoint/service evidence | Current classification |
|---|---|---|
| Common funding-project infrastructure | `backend/funding_api.py`: `GET /funding-project-options`, `POST /funding-projects`, `GET /funding-projects`, `GET /funding-projects/{id}`, `PUT /funding-projects/{id}`, `DELETE /funding-projects/{id}`, `POST /funding-projects/{id}/reactivate`, `GET /funding-dashboard`. Key internal functions include `save_project`, `filtered_projects`, `funding_dict`, and dashboard aggregation helpers. | Confirmed implemented. |
| Funding evidence | `backend/evidence.py`: funding-project evidence list/upload/download/remove handlers, reached through the funding-project evidence route family. | Confirmed implemented. |
| Sponsored Research | Uses the common endpoints with `category=SPONSORED_RESEARCH`; no category-specific service or table. | Confirmed implemented as a shared-category module. |
| Consultancy | Uses the common endpoints with `category=CONSULTANCY`; no category-specific service or table. | Confirmed implemented as a shared-category module. |
| Internal Grants | Uses the common endpoints with `category=INTERNAL_GRANT`; no category-specific service or table. | Confirmed implemented as a shared-category module. |
| Research Proposals | No Proposal API/router/service/model/table found. | Confirmed missing. |
| NBA preview | `backend/nba_reporting_api.py`: funding reporting-options and category report-preview endpoints. | Confirmed implemented as preview/reporting support. |

## 4. Data, validation, and lifecycle assessment

### 4.1 Shared fields that are available today

The shared record stores title, recorded lead/administrative department text, agency, reference number, proposal submission/sanction/start/end dates, status, description, deliverables, outcomes, completion details, internal notes, source URL, investigators, and the category-dependent financial values.

Currencies use nullable `Numeric(14,2)` INR fields, preserving the distinction between an absent value and zero. The model prohibits negative amounts and an end date before a start date. It does not derive amounts or dates automatically.

### 4.2 Status and investigator rules

The accepted statuses are `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `SANCTIONED`, `ONGOING`, `COMPLETED`, `REJECTED`, and `WITHDRAWN`. Sanctioned, ongoing, and completed records require `sanction_date`; sponsored research and consultancy require a PI-level investigator. The API prevents duplicate linked Faculty-plus-role associations and limits designated leads to one.

The API replaces associations during update and validates the new set. It supports one person in multiple distinct roles. Manual investigators are deliberately supported where permitted; they do not increase Faculty Master contributor totals.

There is no enforced status-transition graph, no `REVISION_REQUESTED` or `DEFERRED` state, and no structured record of a transition's date, actor, reason, or attached decision document.

### 4.3 Research Proposals — confirmed missing lifecycle

The current `FundingProject` status values allow a sponsored record to be labelled Draft, Submitted, Under Review, Rejected, or Withdrawn, but this is **not** a proposal module:

- there is no Proposal model, table, API, creation route, detail page, or evidence owner;
- there is no proposal number, scheme/call, research area/domain, abstract, requested duration, revision/deferment history, or proposal-specific status history;
- there is no proposal-to-funded-project link, conversion operation, preservation rule, or duplicate-prevention rule;
- `/proposals` is not configured; and
- the home overview retains a backward-compatible `proposals` total that is sourced from all Sponsored Research records, rather than a separate proposal population.

The label **Total Proposals** in the Sponsored Research overview is therefore misleading: its data source is the shared Sponsored Research record list, including awarded and ongoing projects.

### 4.4 Sponsored Research — current capability

Confirmed implemented:

- sponsored project create/edit/detail and soft lifecycle controls;
- linked/manual PI, Co-PI, administrator, and historical-role handling;
- proposed and sanctioned amounts stored independently;
- financial dashboard aggregation only for award-qualifying statuses (`SANCTIONED`, `ONGOING`, `COMPLETED`);
- general deliverables, outcomes, completion notes and shared evidence categories; and
- faculty, Department, date, status, agency, text, and activity-date/current-Department filters.

Partially implemented or absent:

- no structured scheme/call, research domain, duration/extension, milestone, progress-report schedule, delay, closure, or outcome-to-publication/patent link;
- no structured sanctioned-project change history or amendment record;
- no proposal conversion/link;
- no dedicated agency distribution or sponsored-project trend analytics; and
- no explicit backend rule that category-inapplicable financial fields must remain empty.

### 4.5 Consultancy — current capability

Confirmed implemented:

- shared project lifecycle, investigators, evidence, status filtering, dates, Department filters, and soft deactivation;
- nullable contract/approved amount and amount-received fields;
- dashboard totals that include consultancy financial values only for award-qualifying statuses; and
- Faculty contributor reporting without multiplying a project because it has several investigators.

Partially implemented or absent:

- no structured client organisation/contact, consultancy type, service domain, scope of work, work order, contract terms, deliverable acceptance, invoice, receipt, outstanding balance, tax, overhead, or revenue-share model;
- no invoice/receipt evidence workflow tied to a financial event; and
- no consultancy-specific trend/client/realisation analytics.

### 4.6 Seed Money / Internal Grants — current capability

Confirmed implemented:

- shared project lifecycle with `INTERNAL_GRANT` category;
- Beneficiary as an active investigator role;
- sanctioned and utilised amount fields, nullable fixed precision storage, and award-status financial aggregation; and
- shared evidence categories, date/Department/Faculty filters, pagination, soft deactivation and reactivation.

Partially implemented or absent:

- no distinct application/approval/disbursement/closure workflow;
- no structured internal scheme, approving authority, application/approval number, utilisation milestones, utilisation-certificate status, or internal-grant progress history;
- no controls relating utilised value to sanctioned value; and
- no grant-specific analytics beyond shared totals and Faculty rows.

## 5. Financial integrity assessment

| Concern | Current behavior | Assessment |
|---|---|---|
| Proposed vs sanctioned research amount | Independent nullable fields. | Correct foundational separation. |
| Submitted/under-review money in sanctioned totals | Excluded by award-status predicate. | Correctly guarded. |
| Consultancy contract vs receipts | Independent nullable values. | Foundational fields present; no event or balance reconciliation. |
| Internal sanctioned vs utilised | Independent nullable values. | Foundational fields present; no utilisation control or certificate workflow. |
| Decimal precision | `Numeric(14,2)` amounts, API serialisation for display. | Suitable for high-level INR reporting. |
| Multiple investigators | Records are deduplicated before project and financial aggregation. | Correct aggregation safeguard. |
| Cross-Department shared projects | A project can be visible to each associated Department; UI notes departmental financial totals are non-additive. | Appropriate disclosure, but institution-wide roll-ups must not sum Department totals. |

No installment ledger, invoice ledger, disbursement schedule, receivable ageing, or personal allocation exists. This is consistent with a high-level faculty-performance tracker only if those controls are explicitly out of scope; otherwise, it is a gap rather than a defect.

## 6. Evidence and document handling

Funding evidence is implemented with type-specific categories: `PROPOSAL`, `SANCTION_LETTER`, `AGREEMENT`, `FUNDING_RECEIPT`, `UTILIZATION_CERTIFICATE`, `PROGRESS_REPORT`, `COMPLETION_REPORT`, `OUTCOME_EVIDENCE`, and `OTHER`.

The upload layer validates supported document/image formats, non-empty files, and a 25 MB size limit; uses unique storage paths and SHA-256; checks the owning record; rolls back and removes the stored file if the database operation fails; and provides view/download/remove interactions. Soft deactivation does not remove evidence.

Observed limitations: evidence has no first-class replacement/version operation or per-file narrative fields, and the audited code does not establish user authentication/authorisation policy for sensitive funding documents. The generic detail page also does not visibly render `source_url`, `internal_notes`, or the existing change-log payload.

## 7. Reporting, dashboard, and Faculty integration

### 7.1 Funding overview metrics

The shared dashboard queries a complete filtered project set before pagination. The list page makes a separate request from dashboard totals, so page size and selected list metric should not change dashboard KPIs.

| Category | Count and finance metrics confirmed in current implementation |
|---|---|
| Sponsored Research | Total shared records; submitted/under review; sanctioned; ongoing; completed; proposed amount; sanctioned amount; distinct Faculty contributors. |
| Consultancy | Total shared records; ongoing; completed; contract value; amount received; distinct Faculty contributors. |
| Internal Grants | Total grants; distinct Faculty beneficiaries; sanctioned amount; utilised amount; completed. |

All dashboard finance totals use qualifying award statuses, not merely a non-null amount. Faculty rows count distinct linked Faculty IDs and distinct associated projects; manual investigators are excluded from Faculty Master counts. Role labels preserve agency-provided designations when present.

### 7.2 Date and Department semantics

For general funding filtering/reporting date, the list uses `sanction_date`, then proposal-submission date, then start date. Department scopes support `CURRENT` and `AT_ACTIVITY_DATE`. Activity-date funding attribution specifically requires `sanction_date` and a verified effective Faculty affiliation; records without a qualifying date/affiliation are excluded rather than assigned a fabricated historical Department.

These are defensible existing conventions, but proposal/submission and award/implementation reports need an explicit, separately documented reporting-date policy before an expanded proposal lifecycle is built.

### 7.3 Home, Faculty Details, and NBA reports

- `backend/research_overview.py` reuses the funding dashboard data for home totals. The compatibility key called `proposals` equals the Sponsored Research total, not an independent proposal count.
- `FacultyResearchDetails.tsx` has a Funding Projects tab with linked-record rows, investigator roles and category financial summaries. Amounts are project totals, not a Faculty member's personal allocation.
- `backend/nba_reporting_api.py` supplies preview endpoints for the three funding categories using Academic Year Master records, status eligibility, configurable date basis, CAY mapping, and incomplete-date flags. The inspected implementation is a preview/reporting endpoint, not a generated export workflow.
- No dedicated funding charts for agency mix, status trend, amount trend, or project pipeline were found. The home activity trend is limited to publications, patents, and books.

## 8. Existing verification assets

| Area | Existing focused coverage identified |
|---|---|
| Funding CRUD, roles, date rules, lifecycle, pagination, evidence | `tests/test_funding_projects.py` |
| Department-scoped funding totals and distinct project behavior | `tests/test_department_filtering.py` |
| Faculty Details funding roll-up | `tests/test_faculty_research_details.py` |
| Home/research overview integration | `tests/test_research_overview.py` |
| NBA category/date/CAY/missing-date reporting | `tests/test_nba_funding_reporting.py` |
| Browser sponsored flow, evidence, deactivate/reactivate | `tests/browser/development-funding-functional.spec.ts` |
| Browser dashboard/date/Department controls | `tests/browser/dashboard-rollout.spec.ts`, `tests/browser/dashboard-layout.spec.ts` |

### 8.1 Static test-coverage matrix

This is a source-inspection matrix, not a newly executed test result. The test files above contain coverage for the indicated common-funding behavior.

| Capability | Sponsored Research | Consultancy | Internal Grants | Proposal lifecycle |
|---|---|---|---|---|
| Create/read/update | Existing backend tests cover shared category requests and updates. | Existing backend tests cover category requests and finance fields. | Existing backend tests cover category requests and finance fields. | Missing—no implementation to test. |
| Soft deactivate/reactivate | Backend and sponsored browser flow cover the common lifecycle. | Common endpoint implemented; no dedicated browser flow identified. | Common endpoint implemented; no dedicated browser flow identified. | Missing. |
| Validation/participants | Roles, duplicates, manual/linked investigators, Lead PI limit and required PI rules are covered in `test_funding_projects.py`. | Shared validation is covered; no consultancy-specific validation exists. | Beneficiary compatibility is covered; no internal-grant workflow validation exists. | Missing. |
| Evidence | Update/evidence ownership preservation and a sponsored browser flow are covered. | Shared evidence implementation applies; dedicated category browser coverage not identified. | Shared evidence implementation applies; dedicated category browser coverage not identified. | Missing. |
| Financial totals | Proposed/sanctioned and no-investigator-duplication coverage exists. | Contract/received and no-duplication coverage exists. | Sanctioned/utilised and no-duplication coverage exists. | Missing. |
| Department attribution | Current/activity-date funding scope is covered in Department tests. | Shared scope applies. | Shared scope applies. | Missing. |
| Status transitions/history | Field/status validation only; no transition-history model exists. | Same. | Same. | Missing. |
| Dashboards/KPIs | Shared dashboard, pagination independence, Faculty totals and home integration covered. | Shared dashboard/date controls covered. | Shared dashboard/date controls covered. | Missing. |

The tests do not establish a proposal lifecycle, proposal conversion, milestones, invoices/receipts, consultancy client/work-order data, internal-grant approval workflow, linked research outputs, or complete change history because those facilities do not currently exist.

## 9. Retain without regression

Any future work should retain the shared funding foundation and its important safeguards:

- stable shared project IDs, evidence ownership, and soft-deactivation behavior;
- manual external investigators alongside Faculty Master-linked investigators;
- one Lead PI maximum, multiple Member PI/Co-PI associations, and historical role compatibility;
- nullable fixed-precision amounts and award-status-only financial totals;
- deduplicated parent-project and Faculty aggregation;
- all current Department attribution rules, including uncertainty rather than fabricated history;
- independent list pagination versus KPI summaries; and
- Academic Year Master-backed NBA preview semantics.

## 10. Source evidence inspected

- `backend/models.py`
- `backend/funding_api.py`
- `backend/evidence.py`
- `backend/research_overview.py`
- `backend/dashboard_reporting.py`
- `backend/nba_reporting_api.py`
- `components/FundingEditor.tsx`
- `components/FundingOverview.tsx`
- `components/EvidenceManager.tsx`
- `components/dashboard/FacultyResearchDetails.tsx`
- `components/AppHeader.tsx`
- `app/research-projects/**`, `app/consultancy/**`, `app/seed-money/**`, `app/funding-projects/**`, `app/proposals/page.tsx`
- `migrations/versions/c4d1e8a7b9f2_funding_projects_consultancy_and_internal_grants.py` and subsequent funding migrations
- the tests listed in section 8.

