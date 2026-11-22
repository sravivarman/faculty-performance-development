# Research, Consultancy and Internal Grant Completion Roadmap

**Purpose:** A sequenced plan that extends the existing shared Funding Project foundation without replacing it, duplicating Faculty Master relationships, or rewriting existing records.

## Guiding principles

- Keep `FundingProject`, `FundingProjectFaculty`, shared evidence, fixed-precision amounts, department attribution, and current KPI safeguards as the common funded-work foundation.
- Do not use a sponsored project row as a substitute for a proposal record when the institution needs proposal history and conversion traceability.
- Preserve legacy roles, existing evidence, linked/manual investigators, identifiers, and nullable historical financial values.
- Make new fields additive and optional for existing records. Never infer missing dates, approvals, financial events, or historical affiliations.
- Keep institutional aggregate totals separate from Department-scope views where a shared project is visible to more than one Department.

## Phase 0 — Governance decisions and non-breaking terminology

### Objective

Resolve the semantics that determine the data model, before exposing more navigation or KPIs.

### Decisions required

1. Confirm whether a Proposal is a separate retained record that can produce zero, one, or more funded projects. The audit recommends **yes**.
2. Approve status vocabularies and permissible transitions for proposals, sponsored execution, consultancy, and internal grants.
3. Approve date bases for pipeline, sanction, execution, completion, consultancy award, internal approval, Department activity-date attribution, and financial reporting.
4. Define the minimum financial scope: high-level values only, or minimal invoice/receipt/disbursement events. Do not accidentally build a full institutional ledger.
5. Agree whether outcome links must cover publications, patents, books, and other modules, and who can create them.
6. Agree evidence retention, superseding/version, and access-control policy.

### Low-risk interim correction

Change the current “Total Proposals”/home proposal terminology to “Sponsored Research Projects” until a real proposal population exists. This avoids reporting awarded work as a proposal without changing data or calculations.

**Acceptance criteria:** approved glossary, date policy, role/status matrix, finance boundary, and evidence/access policy signed off.

## Phase 1 — First-class Proposal lifecycle

### Objective

Make Research Proposals a usable, audited process rather than a placeholder.

### Proposed additive design

- Add a `ResearchProposal` parent with a stable ID; proposal number, title, scheme/call, agency, domain/area, abstract, requested amount/duration, submitted/decision dates, structured status, and notes.
- Add proposal investigators, reusing the existing linked/manual person conventions and validated roles where appropriate.
- Add append-only proposal status/review events for submitted, under review, revision requested, deferred, approved/sanctioned, rejected, withdrawn, and resubmitted where approved by policy.
- Add proposal evidence through the existing evidence architecture with a new owner association only where necessary.
- Provide `/proposals`, `/proposals/new`, detail/edit routes, compact filters, list pagination, and clear active/inactive behavior.
- Link `ResearchProposal` optionally to one or more `FundingProject` records. A conversion creates/links a new sponsored project transactionally and never deletes or mutates the proposal's historic facts.

### Migration and safety

Use a reversible additive migration; preserve all existing `FundingProject` IDs, evidence, and historical submitted statuses. Do **not** backfill proposals from existing sponsored records automatically. Offer an explicit administrator-led reconciliation process for historical data, if required.

**Acceptance criteria:** proposal can be created/reviewed/updated with history and evidence; conversion/link maintains both IDs and source evidence; proposal/project dashboards have unambiguous independent totals.

## Phase 2 — Sponsored Research execution and outcome traceability

### Objective

Extend sanctioned research tracking after Phase 1 determines where proposals end and funded execution begins.

### Scope

- Category extension for scheme/call, approved duration, amendments/extensions, milestone/progress updates, delay reason, closure decision, and completion evidence.
- Optional typed links to eligible publications, patents, books/chapters and other agreed outputs. Validate referenced IDs without copying records or assigning attribution.
- A fuller append-only change history for new changes, including investigator-role changes and material financial/status changes.
- Detail-page presentation of source URL, appropriate internal metadata, status timeline, evidence history, and linked outputs.

**Acceptance criteria:** a sanctioned project can evidence progress, extensions, closure, and linked outcomes without changing existing research-record ownership or reporting formulas.

## Phase 3 — Consultancy engagement and collection tracking

### Objective

Add the minimum consultancy-specific structure without replacing the shared project/investigator/evidence base.

### Scope

- Consultancy extension for client organisation/contact, engagement type, domain, scope of work, work order/agreement reference, contract dates/terms, and delivery/acceptance state.
- If approved in Phase 0, minimal invoice/receipt events with amount, due/received date, reference, status, and evidence link; calculated outstanding amount rather than a free-form competing value.
- Consulting dashboard KPIs: engagements, approved/ongoing/completed, contract value, received, outstanding, client/status/date filters, and explicit non-additive Department note.

**Acceptance criteria:** each consultancy can be traced from agreement through delivery and receipt according to the agreed finance boundary; all totals avoid investigator and Department double counting.

## Phase 4 — Seed Money / Internal Grant workflow

### Objective

Make internal grants auditable as an institutional process rather than a generic funded record.

### Scope

- Internal-grant extension for scheme, application number/date, approving authority, approval/disbursement dates, beneficiary/mentor rules, progress milestones, utilisation-certificate state, and closure/recovery notes where institution policy requires them.
- Clearly separated sanctioned, disbursed, and utilised values only if policy needs all three; otherwise retain the existing two high-level fields and add evidence/status validation.
- Internal-grant list/dashboard and Faculty Detail labels that match the approved workflow.

**Acceptance criteria:** an internal grant can demonstrate application, approval, funding/use, progress, certificate and closure decisions without inventing missing historical facts.

## Phase 5 — Reporting, analytics, and reconciliation

### Objective

Turn the completed lifecycles into trustworthy management and accreditation reporting.

### Scope

- Dashboard views for proposal pipeline, sponsored status/value trends, agency distribution, consultancy realisation/outstanding, and internal-grant use—each with explicit date basis and status eligibility.
- Reusable Faculty and Department drill-downs that use stable Faculty Master IDs, preserve manual external contributors separately, and do not multiply shared parents or money.
- Reconciliation indicators for missing decision/sanction dates, missing required evidence, financial anomalies, incomplete affiliation provenance, and orphaned/invalid links.
- Extend NBA preview/reporting only after data definitions are agreed; never infer Academic Year or reporting date for incomplete records.

**Acceptance criteria:** every KPI has a documented population/date/status rule, drill-down row count agrees with its KPI, and Department roll-ups state whether they are non-additive.

## Cross-phase quality gates

| Gate | Required verification |
|---|---|
| Data preservation | Upgrade/downgrade tests; existing FundingProject, investigator, and evidence records remain readable and unchanged. |
| Financial correctness | Fixed-precision test cases; missing versus zero; submitted values excluded from sanctioned totals; no duplication for multiple investigators. |
| Attribution | Linked Faculty counts once per parent; manual investigators remain non-Faculty Master; Department current/activity-date behavior preserves uncertainty. |
| Evidence | File safety, ownership, rollback cleanup, retention through edits/deactivation, and the agreed versioning/access policy. |
| Lifecycle | Allowed/disallowed transitions, date requirements, conversion/link lineage, historical event immutability. |
| UI/browser | Create/edit/detail/evidence/deactivate/reactivate for each category; compact filters, date filters, pagination, all-record mode, KPI isolation, accessible forms. |
| Reporting | List/dashboard/Faculty/NBA populations agree with their documented scope; shared projects/money are not double-counted. |

## Recommended immediate next task

Run a short requirements/design workshop for **Phase 0**, then implement the small terminology correction separately from the first-class Proposal lifecycle. Do not add a Proposals navigation item or proposal KPI until the Proposal entity, status policy, and proposal-to-project relationship are approved.

## Deferred items intentionally outside this roadmap

- Full institutional general ledger, payroll, tax, or procurement system integration.
- Automatic conversion of existing sponsored records into proposals.
- Fabricated historical dates, approvals, amounts, affiliations, or outcome links.
- Replacement of the shared Funding Project foundation or current Faculty Master relationships.

