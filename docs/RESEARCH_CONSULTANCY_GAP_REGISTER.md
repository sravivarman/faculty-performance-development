# Research, Consultancy and Internal Grant Gap Register

**Audit date:** 22 November 2026  
**Status key:** Confirmed missing means no corresponding implementation was found in the current checkout; partial means a general shared field/workflow exists but not the required structured capability.

| ID | Module | Requirement | Current implementation and evidence | Status | Severity | Recommended minimal action | Dependency | Complexity |
|---|---|---|---|---|---|---|---|---|
| FND-001 | Proposals | First-class proposal record and lifecycle | `/proposals` is `UnconfiguredDashboard`; no Proposal model/API/table/routes in `app/proposals/page.tsx`, `backend/models.py`, or `backend/funding_api.py`. | Missing | Critical | Add a separate retained proposal entity and lifecycle. | Product decision on proposal semantics. | Large |
| FND-002 | Proposals / Sponsored | Proposal-to-project conversion and lineage | Shared `FundingProject` has submitted statuses but no proposal foreign key, conversion endpoint, or history preservation. | Missing | Critical | Add an explicit link and transactional create/link conversion. | FND-001, reporting policy. | Large |
| FND-003 | Shared reporting | Truthful proposal labels and counts | `backend/research_overview.py` maps compatibility key `proposals` to sponsored total; `FundingOverview.tsx` labels the sponsored total “Total Proposals.” | Defective | High | Rename interim labels to Sponsored Research Projects; add a proposal KPI only after FND-001. | API/UI contract review. | Small |
| FND-004 | Proposals | Revision/deferment and decision history | `FundingStatus` in `backend/funding_api.py` omits `REVISION_REQUESTED`/`DEFERRED`; `FundingProjectChangeLog` has no decision events. | Missing | High | Approve lifecycle vocabulary and add append-only review events. | FND-001. | Medium |
| FND-005 | Sponsored | Structured execution milestones and extensions | `FundingProject` has free-text deliverables/outcomes/completion details but no milestone/progress/amendment model. | Partial | High | Add optional progress, amendment and closure relations. | Minimum research-execution policy. | Large |
| FND-006 | Sponsored | Linked research outputs | No project-to-publication/patent/book/FDP/output association in models or APIs. | Missing | High | Add typed optional output links with cross-module ID validation. | Cross-module ownership contract. | Medium |
| FND-007 | Consultancy | Client, engagement and work-order details | `FundingProject` has title/agency/reference only; no structured client/contact/category/domain/scope/work order/acceptance fields. | Partial | High | Add consultancy extension fields/tables while reusing common project/investigator/evidence objects. | Consultancy data-definition approval. | Medium |
| FND-008 | Consultancy | Invoice, receipt and outstanding tracking | `contract_amount` and `amount_received` exist in model/API; no invoice/receipt/due-date/overhead/tax/revenue-share/event models. | Partial | High | Decide minimal finance boundary; add invoice/receipt events if required. | Financial-policy decision. | Large |
| FND-009 | Internal Grants | Application, approval, disbursement and closure workflow | Shared category has beneficiary, sanction/utilisation fields and generic evidence only; no internal scheme/application/approval/disbursement/process model. | Partial | High | Add a small internal-grant lifecycle extension. | Internal-grant policy. | Medium |
| FND-010 | Shared | Category-integrity validation | `FundingEditor.tsx` presents category fields, but `FundingProjectInput` permits all shared financial columns. | Partial | Medium | Add non-destructive category-aware validation for new edits. | Legacy-value compatibility rules. | Small |
| FND-011 | Shared finance | Reconciliation of receipts/utilisation | `Numeric(14,2)`, nullable fields and awarded-status gating are correct; no received-vs-contract or utilised-vs-sanctioned warnings/controls. | Partial | Medium | Decide warning versus rule; never rewrite historical values. | Financial-policy decision. | Medium |
| FND-012 | Shared auditability | Complete material change history | `FundingProjectChangeLog` stores update title/status only; `save_project` replaces investigator associations. | Partial | Medium | Record append-only material field/association events for future edits. | Privacy/audit-retention policy. | Medium |
| FND-013 | Shared evidence | Version/replace metadata and contextual detail | `backend/evidence.py` provides safe upload/download/remove; generic funding detail omits source URL/internal notes/change-log and evidence has no version model. | Partial | Medium | Add supersede/version behavior and appropriate detail presentation. | Evidence access/retention policy. | Medium |
| FND-014 | Analytics | Agency, status and amount trends/pipeline | `FundingOverview.tsx` has KPI tables/drilldowns; no funding trend/agency-distribution chart found. | Missing | Medium | Add read-only analytics only after lifecycle/date semantics are agreed. | FND-001 and reporting-date policy. | Medium |
| FND-015 | Shared reporting | Explicit date-basis policy | `filtered_projects` uses sanction/submission/start fallback; activity-date Department scope requires sanction date. | Partial | Medium | Label/document report-specific date basis and add surface-specific tests. | Reporting policy. | Small |
| FND-016 | Shared integrity | Database-level manual-investigator duplicate defence | API validation checks manual identity; nullable `faculty_id` means the association unique key cannot fully enforce manual duplicates in SQLite. | Partial | Low | Retain API guard; assess DB constraint only if non-API writers are introduced. | Cross-database portability design. | Medium |
| FND-017 | Shared evidence | Institutional access policy | File safety/ownership are implemented in `backend/evidence.py`; user/role authorisation was not demonstrated in audited scope. | Untested | Low | Conduct separate access-control audit before making confidentiality claims. | Authentication/RBAC policy, outside current module scope. | Medium |

## Confirmed strengths, not gaps

- Shared funding CRUD is category-aware in the user interface and uses stable project/evidence ownership.
- Proposed and sanctioned research amounts are distinct and nullable; submitted and under-review records do not inflate sanctioned financial totals.
- Contract/received and sanction/utilised pairs exist for consultancy and internal grants.
- Parent-project and Faculty totals are deduplicated, including across multiple investigator roles.
- Manual external investigators are not incorrectly counted as Faculty Master contributors.
- Department scope deliberately avoids inventing unverified historical affiliations.
- Soft deactivation/reactivation and shared evidence handling are present.

## Priority interpretation

1. Resolve FND-001 through FND-004 together before presenting any “Proposals” navigation or proposal KPI as live functionality.
2. Resolve FND-005/FND-006 for research execution evidence, FND-007/FND-008 for consultancy, and FND-009 for internal grants according to the institution's minimum operational record standard.
3. Address terminology, category integrity, financial warnings, history, and analytics after the underlying lifecycle decisions are made.

