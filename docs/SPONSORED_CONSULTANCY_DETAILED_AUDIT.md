# Sponsored Research and Consultancy Detailed Audit

**Audit date:** 22 November 2026  
**Scope:** Sponsored Research and Consultancy only, using the existing shared `FundingProject` foundation.  
**Audit mode:** Read-only source and test inspection. No source code, migration, database, evidence file, navigation, or record was changed.

## 1. Approved scope applied to this audit

This report supersedes the proposal-related recommendations in the earlier Research/Consultancy audit **only for the approved institutional scope**:

- Sponsored Research is one record lifecycle in `FundingProject` with category `SPONSORED_RESEARCH`; Draft, Submitted, Under Review, Sanctioned, Ongoing, Completed, Rejected, and Withdrawn are states of that record.
- Consultancy remains `FundingProject` category `CONSULTANCY`.
- High-level values are sufficient: Sponsored Research uses proposed and sanctioned amounts; Consultancy uses contract/approved and amount received.
- Evidence is optional and must stay optional.
- No separate Proposal model, proposal-to-project conversion, invoice/receipt ledger, finance reconciliation system, mandatory evidence checklist, or replacement investigator architecture is required.

## 2. Classification and verification basis

| Classification | Meaning |
|---|---|
| `IMPLEMENTED_AND_VERIFIED` | Source behavior and a current isolated test execution both completed successfully in this audit. No item receives this classification in this run. |
| `IMPLEMENTED_NOT_TESTED` | Source implementation was inspected; a focused test may exist, but this audit did not obtain a completed execution result. |
| `PARTIALLY_IMPLEMENTED` | The foundation exists but does not cover the approved requirement fully. |
| `DEFECTIVE` | Current behavior or wording can misstate data or hide available information. |
| `MISSING` | No implementation found for an approved requirement. |
| `OPTIONAL_ENHANCEMENT` | Useful only if it supports Department performance tracking; not required for correctness. |
| `NOT_REQUIRED` | Explicitly excluded by the approved scope. |

The test runner was not successfully verified in this audit. `.venv/pyvenv.cfg` points to Python 3.14.7 and `python --version` runs, but pytest startup emits `Failed to find real location of ...Python314\python.exe` and produced no collection/result summary. This is recorded as an environment issue, not an application-test result.

## 3. Verified architecture

| Layer | Sponsored Research | Consultancy | Shared evidence |
|---|---|---|---|
| Routes | `/research-projects`, `/research-projects/new` | `/consultancy`, `/consultancy/new` | Generic detail/edit: `/funding-projects/[id]`, `/funding-projects/[id]/edit` |
| UI | `FundingOverview` with `SPONSORED_RESEARCH`; `FundingEditor` | `FundingOverview` with `CONSULTANCY`; `FundingEditor` | `EvidenceManager` on detail and edit routes |
| API | Shared `/funding-projects`, `/funding-dashboard`, `/funding-project-options` filtered by category | Same shared endpoints | `/funding-projects/{id}/evidence` through shared evidence router |
| ORM/table | `FundingProject` / `funding_projects` | Same | `EvidenceFile.funding_project_id` |
| Investigators | `FundingProjectFaculty` / `funding_project_faculty` | Same | N/A |
| Reporting | Funding dashboard, home overview, Faculty Research Details, NBA preview | Same | Evidence does not affect KPIs |

The three funding categories share the same record, association, evidence, and reporting infrastructure. This is maintainable for the approved scope: common filters, Department attribution, pagination, evidence safety, and Faculty aggregation are implemented once. Category-specific financial fields are stored on the same parent but the editor exposes only the relevant pair.

### Backend and data evidence

- `backend/models.py:482-551` defines the parent, investigator association, change log, constraints, precision and foreign keys.
- `backend/funding_api.py:23-433` defines input validation, CRUD, filters, status/financial aggregation, deactivation/reactivation, and dashboard data.
- `backend/evidence.py:82-170` implements optional funding evidence upload/list/download/removal.
- `migrations/versions/c4d1e8a7b9f2_funding_projects_consultancy_and_internal_grants.py` creates the common foundation; `d9e6f1a4c782`, `e2b7c4d9a613`, `f14e9c2a7b35`, and `a4c8f7e2d6b1` add manual investigators, role preservation, and category financial amounts.

## 4. Sponsored Research assessment

### Implemented by source inspection

- **Single record lifecycle:** the editor offers exactly the approved eight statuses. `DRAFT` is the default.
- **Research/project details:** title, Funding Agency, Recorded Lead / Administrative Department, reference/sanction number, proposal submission, sanction/approval, start and end dates, description, deliverables, outcomes, completion details, source URL, and internal notes are stored.
- **High-level finance:** proposed/requested and sanctioned amounts are independent nullable `Numeric(14,2)` INR values. Missing differs from zero.
- **Award isolation:** sanctioned, ongoing, and completed records are the only records contributing to sanctioned financial totals. Submitted and under-review proposed amounts are retained but excluded from award totals.
- **Investigators:** multiple linked Faculty Master and manual external investigators are supported. Lead PI, Member PI, Co-PI, and Admin PI are active UI roles; a single lead is enforced; multiple distinct roles for the same Faculty member are allowed; exact Faculty-plus-role duplicates are rejected.
- **Lifecycle safety:** all valid stages can be created directly. Submitted records need not have a sanction date. Sanctioned, Ongoing and Completed records require one. Updating preserves the project ID and evidence relationship.
- **Optional evidence:** evidence is not part of create/update validation and can be added later.

### Partial or corrective items

1. **The first KPI is labelled “Total Proposals” but counts every Sponsored Research record**, including sanctioned, ongoing, completed, rejected, and withdrawn records. Under the approved single-module design this is a terminology defect, not a data-model defect. “Total Research Records” or “Total Sponsored Research Records” is accurate.
2. **Status/date coherence is intentionally minimal.** The backend checks end date is not before start date and requires a sanction date for sanctioned/ongoing/completed records. It does not require a start/end date for Completed or prevent a Draft/Rejected/Withdrawn record from retaining sanction/date/amount values. This protects legacy data but can leave confusing new-entry combinations. A non-destructive status-aware hint or narrowly approved validation is an essential data-quality improvement only if institutional policy defines the combination rules.
3. **Funding scheme, research domain, and a separately labelled abstract are absent.** Existing `funding_agency`, `reference_number`, and `description` can hold related information, but they are not semantically separate. No approved reporting need was established, so these are not essential missing fields.
4. **Actual completion information** is free text (`completion_details`); there is no distinct actual-completion date. The approved requirement asks for completion information, which is met; a date is optional unless reports need date-based completion metrics.

## 5. Consultancy assessment

### Implemented by source inspection

- The category has its own route, Add page, overview labels, finance labels, filters and back navigation while reusing the shared foundation.
- “Client / Sponsoring Organization” maps to `funding_agency`; reference/work-order-like values map to `reference_number`; description and deliverables capture scope/outcomes without duplicating columns.
- Contract/approved amount and amount received are separate nullable numeric fields. Award-status gating applies to dashboard financial totals, so a draft/submitted consultancy does not inflate received/contract values.
- The same PI-level requirement, linked/manual investigator support, optional evidence, Department/Faculty filters, pagination, deactivation/reactivation, and Faculty reporting are present.

### Partial or corrective items

1. There is no distinct consultancy category, domain, client type, contact, or formal work-order field. This is **not automatically a schema gap**: existing client/organisation, reference number, and description fields cover the approved core record. Category-specific label/help-text refinement should be considered before adding columns.
2. The screen does not display a derived `contract_amount - amount_received` value. A clearly labelled **Indicative unreceived balance** would be a useful optional display calculation; it must not be described as an audited receivable and need not be stored.
3. Consultancy detail currently displays finance, dates, description, deliverables/outcomes, investigators, and evidence. `source_url` is returned by the API and editable, but is not rendered in the generic detail page. This is a small detail-view defect for either category.

## 6. Lifecycle, validation, and integrity

| Requirement | Current behavior | Classification |
|---|---|---|
| Draft → Submitted → Under Review → Sanctioned → Ongoing → Completed vocabulary | All eight states are database-constrained and offered by the editor. | `IMPLEMENTED_NOT_TESTED`; focused validation tests exist. |
| Rejected / Withdrawn outcomes | Both states exist and are filterable. They remain normal active records unless separately deactivated. | `IMPLEMENTED_NOT_TESTED`. |
| Submitted without sanction | Accepted by input validation. | `IMPLEMENTED_NOT_TESTED`; source behavior inspected. |
| Sanction required for sanctioned/ongoing/completed | API rejects those statuses without `sanction_date`. | `IMPLEMENTED_NOT_TESTED`; focused tests exist. |
| End after start | API and database constraint enforce it. | `IMPLEMENTED_NOT_TESTED`; source behavior inspected. |
| Status transition history | General `FundingProjectChangeLog` records create/update/deactivate/reactivate, but an update snapshot has only title/status. | `PARTIALLY_IMPLEMENTED`; append-only status history is optional. |
| Soft inactive versus Withdrawn | `is_active` controls visibility; Withdrawn is a project status. They are distinct technical concepts, but the UI does not explain the distinction. | `PARTIALLY_IMPLEMENTED`; small help-text improvement only. |
| Existing values during update | Full editor prefill and `PUT` save are used; evidence ownership remains on the same project. | `IMPLEMENTED_NOT_TESTED`; focused preservation tests exist. |
| Cross-category financial payloads | API schema accepts every shared amount field; editor hides irrelevant fields by category. | `PARTIALLY_IMPLEMENTED`; see SC-002. |

No complex transition engine is required by the approved scope. A complete historical “ever submitted” KPI also cannot be derived from the current state alone; current data can accurately report records **currently** Submitted or Under Review.

## 7. KPI and reporting audit

### Funding Overview

`FundingOverview.tsx` retrieves records and the dashboard independently. `funding_dashboard_data` receives the full filtered record set before pagination, then returns project totals, financial totals, faculty rows and role counts. A KPI-specific list filter never becomes a dashboard-summary filter.

| Current KPI | Actual calculation | Correctness |
|---|---|---|
| Total Proposals (Sponsored) | Count of all matching `SPONSORED_RESEARCH` parents. | **Data correct; label defective.** |
| Submitted / Under Review | Current records whose status is `SUBMITTED` or `UNDER_REVIEW`. | Correct current-state count; not a historical submissions count. |
| Sanctioned Projects | Current records in `SANCTIONED`, `ONGOING`, or `COMPLETED`. | Correct award-state population. |
| Ongoing / Completed | Exact status counts. | Correct. |
| Total Sanctioned Amount | Sum of `sanctioned_amount` only over award-state records. | Correct. |
| Consultancy total | Count of all matching `CONSULTANCY` parents. | Correct. |
| Total Contract Value / Amount Received | Corresponding fields summed only over award-state consultancy records. | Correct for stated high-level values. |
| Faculty Contributors | Distinct linked Faculty Master IDs; projects per person are distinct. Manual investigators are excluded. | Correct; does not imply personal allocation. |

Records are ordered by reporting date (`sanction_date`, else `proposal_submission_date`, else `start_date`) then ID. Filters include free-text, Faculty, Department, current/activity-date attribution, recorded administrative department, organisation/client, current status, active state, shared date range, page size and page. There is no user-selectable sort, agency distribution, or year-bucket chart; those are optional, not required for correctness.

### Home, Faculty Details, Department and NBA

- Home overview reuses the category dashboard data. Its backwards-compatible `proposals` response key equals sponsored-record count; the home UI uses the clearer research-projects label. API consumers should treat this key as compatibility-only.
- Faculty Details lists only Faculty Master-linked funding associations and clearly says funding figures are **project totals, not personal allocations**. It preserves actual investigator roles and links to detail pages.
- Department filtering uses one parent-project predicate, avoiding association-row duplication. A shared project may appear in each eligible Department but Department financial totals are explicitly non-additive. Activity-date mode uses verified primary affiliation at sanction date and excludes unverified history rather than fabricating it.
- NBA preview reuses Academic Year Master, explicit category/date-basis policy, eligible award statuses, and incomplete-date reporting. It is a preview service, not an accounting or export system.

## 8. Investigator and Department attribution audit

The shared association is appropriate for the approved scope. It preserves display order, manual investigator name/department/institution, optional agency role title, linked Faculty ID, and designated lead. A linked Faculty selection is stable by ID; `FacultySelector` also displays employee ID, Department code when available, and historical status.

The backend requires a PI-level role for Sponsored Research and Consultancy. Linked and manual identities are mutually exclusive. Existing `PI` and `CO_INVESTIGATOR` rows remain readable and editable only as historical roles, while new associations use the five approved active roles. The partial unique designated-lead index and API validation prevent two leads.

Current Department is shown in the Faculty selector when supplied by Masters and in the Faculty Details header. Project detail shows manual investigator department/institution values but not the current Department of each linked Faculty member; this is acceptable because the detail page should not imply a current Department is the Department at project activity date.

## 9. Optional evidence audit

Evidence is optional in both the frontend and API. A record can be created, updated, sanctioned, completed, deactivated and reactivated without it. Later uploads accept PDF, PNG, JPG/JPEG, and DOCX up to 25 MB; categories include proposal, sanction letter, agreement, funding receipt, utilisation certificate, progress/completion report, outcome evidence and other.

Evidence is linked to exactly one parent through `EvidenceFile.funding_project_id`; ownership checks prevent cross-record removal/download; SHA-256 and a unique storage path are recorded; invalid/oversized/empty upload handling removes a partially written file; and normal edit/deactivation preserves evidence. Existing tests cover update preservation and ownership rejection. No mandatory evidence score or gate exists, which conforms to the approved scope.

## 10. UI/UX audit

### Strengths

- One reusable editor keeps shared investigator, date, validation, currency and save behavior consistent.
- Compact grouped sections separate project details, investigators, and financials/outcomes.
- Submission failures retain the draft in state and show an alert; success returns to the persisted detail page.
- The Faculty selector is searchable and displays identifier/Department context; manual external collaborators remain possible for Sponsored Research and Consultancy.
- Date range controls remain separate from compact list filters; filter changes reset pagination.
- Detail pages expose status, reference, dates, relevant financial pair, description/deliverables/outcomes/completion information, investigator roles, optional evidence, and lifecycle actions.

### Small usability findings

- Rename “Reference / sanction number” by category where practical: Sponsored Research may retain that wording; Consultancy could use “Reference / work-order number” without a schema change.
- Detail pages should render a valid source URL when present. Do not expose `internal_notes` by default without an explicit policy, because it is clearly named internal.
- Labels state INR, and detail values use INR formatting; entry fields are plain decimal inputs. This is acceptable, although a lightweight formatted preview is optional.
- The overview has deterministic sorting but no sort chooser. A sort chooser is optional; it is not needed to make Department tracking correct.

## 11. Database and API integrity

The parent has required title/category/recorded department/status, category and status check constraints, INR-only currency, non-negative amounts, date ordering, indexes for category/status/relevant dates/active, and soft deactivation. Investigator links cascade when a project is permanently deleted, evidence links cascade with their parent, and the one-evidence-owner check prevents multi-owner evidence rows.

The input model applies maximum lengths to title, administrative department, agency, reference number, manual identity fields and designation; validates participant identity/duplication, PI-level participation, designated lead, sanction date for award stages, and date ordering. All fields are full-replacement `PUT` payload values rather than patch semantics.

The practical gap is category integrity: a direct API client can submit Sponsored/Consultancy records with another category's shared financial field because the Pydantic request shape is deliberately broad. The UI does not present those fields. The smallest backward-compatible correction is to reject newly supplied irrelevant values or warn/ignore them by approved policy while preserving already stored historical values; no destructive data change is justified.

## 12. Reassessment of prior gap IDs

| Earlier ID | Revised classification under approved scope | Rationale |
|---|---|---|
| FND-001 separate Proposal model | `NOT_REQUIRED` | One lifecycle record is the approved institutional design. |
| FND-002 proposal conversion/link | `NOT_REQUIRED` | No separate proposal/project entities are wanted. |
| FND-004 complex decision history | `OPTIONAL_ENHANCEMENT` | Current statuses suffice; append-only history is useful only if operational need is confirmed. |
| FND-005 milestones/extensions | `OPTIONAL_ENHANCEMENT` | Free-text deliverables/outcomes/completion details satisfy current performance tracking. |
| FND-006 output links | `OPTIONAL_ENHANCEMENT` | No confirmed reporting requirement for relational output attribution. |
| FND-007 consultancy descriptive expansion | `OPTIONAL_ENHANCEMENT` | Agency/reference/description reuse should be improved first through labels/help text. |
| FND-008 invoice/receipt accounting | `NOT_REQUIRED` | High-level contract and received amounts are the approved finance boundary. |
| FND-009 extensive internal-grant workflow | `NOT_REQUIRED` for this audit | Outside Sponsored/Consultancy scope; no action proposed here. |
| FND-010 category integrity | `PARTIALLY_IMPLEMENTED` | Small backward-compatible API validation improvement is justified. |
| FND-011 financial reconciliation | `NOT_REQUIRED` beyond an optional indicative balance | No ledger or audited receivable is required. |
| FND-012 complete change history | `OPTIONAL_ENHANCEMENT` | Existing change log is sufficient for current scope. |
| FND-013 evidence versioning | `NOT_REQUIRED` | Optional evidence upload/remove is already adequate. |
| FND-014 analytics | `OPTIONAL_ENHANCEMENT` | Add only where data supports a useful Department decision. |
| FND-015 date-basis clarity | Retained as `PARTIALLY_IMPLEMENTED` | Rules are implemented but deserve clearer user-facing documentation. |

## 13. Existing test coverage and execution status

| Area | Existing tests identified | Audit execution result |
|---|---|---|
| CRUD, roles, validation, pagination, lifecycle, finance, evidence, legacy roles | `tests/test_funding_projects.py` | Not completed in this audit due launcher warning/no pytest summary. |
| Department project and money deduplication | `tests/test_department_filtering.py::test_funding_apis_scope_distinct_projects_and_financial_totals_by_department` | Not newly executed. |
| Home overview reuse | `tests/test_research_overview.py::test_home_overview_reuses_funding_fdp_and_certification_reporting_rules` | Not newly executed. |
| Faculty Details | `tests/test_faculty_research_details.py` and funding test coverage | Not newly executed. |
| NBA reporting policy | `tests/test_nba_funding_reporting.py` | Not newly executed. |
| Browser sponsored workflow | `tests/browser/development-funding-functional.spec.ts` | Not newly executed. |
| Browser date/Department dashboards | `tests/browser/dashboard-rollout.spec.ts`, `tests/browser/dashboard-layout.spec.ts` | Not newly executed. |

### Exact local verification commands

```powershell
$testDir = ".test-tmp-sponsored-consultancy-$([guid]::NewGuid().ToString('N'))"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $testDir `
  tests\test_funding_projects.py `
  tests\test_department_filtering.py `
  tests\test_research_overview.py `
  tests\test_faculty_research_details.py `
  tests\test_nba_funding_reporting.py
npm run test:e2e -- tests/browser/development-funding-functional.spec.ts tests/browser/dashboard-rollout.spec.ts tests/browser/dashboard-layout.spec.ts
```

Before relying on the Python result, diagnose why the configured venv emits the base-interpreter location warning. This audit did not recreate or modify the virtual environment.

## 14. Audit conclusion

The shared Funding Project foundation is already appropriate for Department-level Sponsored Research and Consultancy tracking. It should be retained. The minimum corrective work is limited to accurate Sponsored Research wording, category-aware API integrity, user-facing date/status clarity, and source-URL visibility. Consultancy can be more convenient through label/help-text refinement and, if desired, a non-persistent indicative balance. Agency/year charts, status-history events, separate descriptive fields, milestones and output links are optional enhancements—not prerequisites for correct current reporting.

