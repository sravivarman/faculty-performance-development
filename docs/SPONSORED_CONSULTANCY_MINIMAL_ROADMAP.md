# Sponsored Research and Consultancy Minimal Completion Roadmap

This roadmap is deliberately limited to three small phases. It retains the existing `FundingProject` model, category structure, investigator association, optional evidence system, and high-level financial fields.

## Phase 1 — Correct wording, visibility, and basic data integrity

**Goal:** Make current records accurately understandable without changing their meaning.

- Rename the Sponsored Research total KPI from “Total Proposals” to “Total Research Records” or “Total Sponsored Research Records.” Keep existing API compatibility keys intact.
- Render `source_url` on the generic funding detail page when present. Do not surface `internal_notes` without a separate policy decision.
- Add category-aware handling for newly submitted irrelevant financial fields. The preferred behavior must preserve all existing values and never silently clear historical data.
- Add compact status/date guidance; introduce only policy-approved validation. Continue allowing historical records to retain data that would not be entered on a fresh record.
- Add focused backend and browser regression coverage for labels, URL display, category integrity, and status/date cases.

**Schema impact:** None expected.  
**Data impact:** None; validation must be backward-compatible.

## Phase 2 — Consultancy usability refinements

**Goal:** Improve entry clarity using existing fields before adding any schema.

- Use category-specific help text: client/sponsoring organisation, reference/work-order number, description/scope, deliverables, and completion remarks.
- If useful to the Department, show a non-persistent “Indicative unreceived balance” derived from contract minus received. It must not affect KPIs and must not be presented as audited finance.
- Review labels and empty states for Draft, Submitted, Under Review, Rejected and Withdrawn to distinguish record status from soft deactivation.
- Verify manual/Faculty-linked investigator flows, agency designation display, inactive historical Faculty, optional evidence upload later, and edit prefill.

**Schema impact:** None.  
**Data impact:** None.

## Phase 3 — Reporting clarity and only useful analytics

**Goal:** Make Department-level figures explainable, not decorative.

- Display a consistent date-basis explanation across overview, Faculty Details, Department attribution, and NBA preview contexts.
- Add Rejected/Withdrawn current-state metrics, an agency/client distribution, or a year summary only if the Department confirms the decision/use case and the existing data population makes it meaningful.
- Preserve current safeguards: totals are unpaginated, one parent project counts once, manual external investigators are not Faculty Master contributors, shared Department financial values are non-additive, and submitted values do not inflate award totals.
- Extend isolated tests for any selected metric’s population, date basis, Faculty drill-down, Department scope, and pagination independence.

**Schema impact:** None expected for summary views.  
**Data impact:** None.

## Explicitly deferred / excluded

- Separate Research Proposal records or conversion workflows.
- Invoice, receipt, tax, revenue-share, procurement, or financial ledger work.
- Mandatory evidence, evidence-completeness scoring, or document gates.
- Separate investigator infrastructure.
- Milestone, extension, status-history, research-output-link, or additional consultancy field schemas unless a later approved reporting requirement proves they are necessary.

## Definition of done for the current scope

Sponsored Research and Consultancy are complete for Department faculty-performance tracking when lifecycle labels match their actual single-record semantics; only relevant financial fields can be newly entered; optional evidence and existing investigators remain stable; source information is visible where stored; and KPI, Faculty, Department and NBA views agree on date/status population without multiple-investigator duplication.

