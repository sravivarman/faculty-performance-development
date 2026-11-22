# Sponsored Research and Consultancy Field Matrix

**Source basis:** Current `FundingProject` model, `FundingProjectInput`, `FundingEditor`, `FundingOverview`, generic funding detail page, dashboard services, and migrations.  
**Legend:** A/E = Add/Edit; D = Detail; L = List; R = dashboard, Faculty Details, home, or NBA reporting. “—” means not exposed in that surface.

## 1. Common record and timeline fields

| User-facing field | Database / API | Type / default / validation | Sponsored Research surfaces | Consultancy surfaces | Filter / reporting use | Audit finding |
|---|---|---|---|---|---|---|
| Project title | `FundingProject.title`; `FundingProjectInput.title` | Text; required; 1–2000 chars; no default | A/E, D, L | A/E, D, L | Search; record label in all reports | Implemented. |
| Recorded Lead / Administrative Department | `department` | Text; required; 1–250 chars | A/E, D header/L secondary text | A/E, D header/L secondary text | Recorded-department filter; distinct from Master attribution | Implemented; wording correctly explains distinction. |
| Funding Agency / Client / Sponsor | `funding_agency` | Nullable text; ≤2000 chars | “Funding Agency” A/E; D/L | “Client / Sponsoring Organization” A/E; D/L | Organisation filter; home/Faculty/NBA record data | Implemented. Adequate core client field. |
| Reference / sanction number | `reference_number` | Nullable text; ≤250 chars | A/E, D | A/E, D | Not filterable/reported aggregate | Implemented. Consultancy label could be “Reference / work-order number” without schema change. |
| Status | `status` | Required constrained string; default `DRAFT`; eight approved values | A/E, D, L | A/E, D, L | Status filter and dashboard counts | Implemented; minimal date coherence only. |
| Proposal submission date | `proposal_submission_date` | Nullable indexed date | A/E, D, L as fallback reporting date | A/E, D, L as fallback reporting date | Date range fallback; NBA override | Implemented. Useful within single lifecycle. |
| Sanction / approval date | `sanction_date` | Nullable indexed date; required for sanctioned/ongoing/completed | A/E, D, L | A/E, D, L | Primary reporting date; award/KPI/Department activity date/NBA default | Implemented. |
| Project start date | `start_date` | Nullable indexed date | A/E, D | A/E, D | Third reporting-date fallback; NBA override | Implemented. |
| Project end date | `end_date` | Nullable date; must be ≥ start date when both given | A/E, D | A/E, D | Faculty Details project period | Implemented. Represents expected completion, not actual completion date. |
| Description | `description` | Nullable text | A/E, D | A/E, D | Not a structured filter/report field | Implements abstract/scope free text. |
| Deliverables | `deliverables` | Nullable text | A/E, D | A/E, D | Not aggregate reporting | Implemented. |
| Outcomes | `outcomes` | Nullable text | A/E, D | A/E, D | Not aggregate reporting | Implemented. |
| Completion details | `completion_details` | Nullable text | A/E, D | A/E, D | Not aggregate reporting | Implements actual completion narrative; no distinct completion date. |
| Source URL | `source_url` | Nullable text; browser `url` control | A/E only | A/E only | API response includes it | **Detail visibility defect:** not rendered on generic detail. |
| Internal notes | `internal_notes` | Nullable text | A/E only | A/E only | API response includes it | Intentionally not displayed in detail; no change recommended without access-policy decision. |
| Active/inactive | `is_active` | Boolean; default true | D; list include-inactive filter | D; list include-inactive filter | Default active-only; deactivate/reactivate endpoints | Implemented. Distinct from Withdrawn status. |

## 2. Financial fields

| User-facing field | Database / API | Data rules | Sponsored Research | Consultancy | Reporting behavior | Audit finding |
|---|---|---|---|---|---|---|
| Proposed / requested amount | `proposed_amount` | Nullable `Numeric(14,2)` INR; non-negative; absent ≠ zero | A/E, D | Hidden in UI | Sponsored dashboard and Faculty Details; all record statuses | Implemented and distinct from sanction. |
| Sanctioned amount | `sanctioned_amount` | Nullable `Numeric(14,2)` INR; non-negative | A/E, D | Hidden in UI | Sum only for Sanctioned/Ongoing/Completed sponsored records | Implemented. Existing pre-sanction historical amount is retained and visibly excluded from award KPI. |
| Consultancy contract / approved amount | `contract_amount` | Nullable `Numeric(14,2)` INR; non-negative | Hidden in UI | A/E, D | Sum only for award-state consultancy records | Implemented. |
| Amount received | `amount_received` | Nullable `Numeric(14,2)` INR; non-negative | Hidden in UI | A/E, D | Sum only for award-state consultancy records | Implemented. No invoice/receipt ledger is required. |
| Amount utilized | `amount_utilized` | Nullable `Numeric(14,2)` INR; non-negative | Hidden in UI | Hidden in UI | Not used by these two category dashboards | Not applicable to approved Sponsored/Consultancy UI. |
| Currency | `currency` | Required `INR` only; default INR | Implicit | Implicit | Detail formatter and reporting | Implemented. |

**Category integrity note:** The API payload accepts all five amount fields because the underlying parent is shared. The editor exposes the appropriate pair only. A direct client can nevertheless submit irrelevant category fields. Rejecting or warning on new irrelevant values while preserving historical rows is a small improvement; new columns are not needed.

## 3. Investigator fields and relationships

| User-facing concept | Relationship/API | Validation and persistence | Sponsored Research | Consultancy | Reporting/attribution | Audit finding |
|---|---|---|---|---|---|---|
| Faculty Master investigator | `FundingProjectFaculty.faculty_id` | Nullable FK to `faculty`; stable ID; linked/manual identity mutually exclusive | Searchable selector in A/E | Same | Faculty contributor totals and Faculty Details only include linked Faculty | Implemented. |
| Manual external investigator | `investigator_name`, `department_name`, `institution_name`, `affiliation_type=MANUAL` | Name required if no Faculty ID; allowed for both categories | A/E/D | A/E/D | Excluded from Faculty Master counts | Implemented. |
| Lead PI | `role=LEAD_PI`, `is_designated_lead` | Automatically designates lead; partial unique lead index; at most one | A/E/D | A/E/D | PI display, Faculty roles | Implemented. |
| Member PI | `role=MEMBER_PI` | PI-level role; multiple permitted | A/E/D | A/E/D | PI display, Faculty roles | Implemented. |
| Co-PI | `role=CO_PI` | Multiple permitted | A/E/D | A/E/D | Contributor roles | Implemented. |
| Admin PI | `role=ADMIN_PI` | Distinct role, not automatic scientific lead | A/E/D | A/E/D | PI display/Faculty role list | Implemented. |
| Agency designation | `agency_role_label` | Optional, ≤100 chars; preserves manual agency wording | A/E/D | A/E/D | Displayed instead of normalized role where supplied | Implemented. |
| Investigator order | `display_order` | Rebuilt in selected order during save | Move controls A/E; ordered D | Same | Detail and API retain ordering | Implemented. |
| Exact duplicate role | `(funding_project_id, faculty_id, role)` plus API identity validation | Same Faculty can have distinct roles; same role cannot duplicate | A/E/API | A/E/API | Prevents association inflation | Implemented. |
| Historical role | `PI`, `CO_INVESTIGATOR` | Database/API readability preserved; unavailable to new associations | Edit/detail historical display | Same | Role reports preserve historical meaning | Implemented. |

## 4. Filters, list, detail and report surfaces

| Surface | Sponsored Research | Consultancy | Verification/findings |
|---|---|---|---|
| Overview KPIs | Total (mislabelled “Total Proposals”), current submitted/under review, award-state sanctioned, ongoing, completed, sanctioned amount, Faculty contributors | Total, ongoing, completed, contract value, received, Faculty contributors | Pagination-independent dashboard query; no investigator-row multiplication. |
| List filters | Search, Faculty, Department, Department attribution mode, recorded department, agency, status, include inactive, shared date range, KPI metric | Same with client wording | Correct; every filter change resets to page 1. |
| Pagination | 10/25/50/All; deterministic reporting-date/ID ordering | Same | Implemented server-side. |
| Detail | Dates, status, reference, relevant financial pair, narrative fields, investigators, optional evidence, edit/deactivate/reactivate | Same | Source URL omission is the only confirmed presentation gap. |
| Faculty Details | Associated projects, roles, record date/period, relevant financial fields, category summary | Same | Project values explicitly not personal allocations. |
| Home overview | Sponsored count/award total via shared funding summary; compatibility `proposals` key also supplied | Consultancy count/received amount via shared summary | The compatibility key must not be treated as a separate proposal population. |
| NBA preview | Sponsored table with sanction default and selectable date basis | Consultancy table with approval/award wording and same configurable basis | Uses Academic Year Master; flags incomplete date data. |
| Agency/client aggregation | Filter/options only | Filter/options only | No distribution KPI/chart; optional only if it informs Department decisions. |
| Year trend | Shared date range and NBA academic-year grouping | Same | No overview year buckets/trend chart; optional only. |

## 5. Explicitly not required for this approved scope

- Separate Proposal model, conversion route, or separate proposal evidence owner.
- Invoice, receipt, payment, tax, overhead, revenue-share, procurement, or accounting ledger fields.
- Mandatory evidence, evidence-completeness scoring, or upload gates.
- Standalone investigator table or replacement Faculty-selection workflow.
- Milestone, extension, output-link, client-contact, or status-history schemas unless a future confirmed Department reporting requirement justifies them.

