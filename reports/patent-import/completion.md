# Historical patent import — completed 3 October 2026

## Backup

Verified SQLite online backup: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\backups\pre_patent_import_20261003_002952.db`. Integrity and foreign-key checks passed. Application and import use `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\faculty.db`.

## Schema / Claim Rule Change

Migration `a03d26e71001` removes only the one-claimant patent index. Existing inventor rows and claims are preserved. Unique patent/faculty and patent/inventor-order constraints, master foreign keys and department-Faculty-only claimant checks remain. Multiple checkbox selections replace the patent radio control; tables display every claimant. Historical/inactive Faculty remain eligible. Publications and Books claimant rules are unchanged.

## Dry-Run Reconciliation

Both initial and final dry runs found 9 new patents, 55 inventors and zero ambiguous mappings. Complete per-record inputs and mapping reasons are in `final-dry-run.json`. Nothing was imported until reconciliation and relevant tests passed.

## Imported Patents

| Patent Number | Type | Status | Inventors | Faculty claimants |
|---|---|---|---:|---:|
| 202641060300 A | UTILITY | PUBLISHED | 6 | 5 |
| 202641060303 A | UTILITY | PUBLISHED | 6 | 6 |
| 483689-001 | DESIGN | PUBLISHED | 5 | 1 |
| 202541124572 A | UTILITY | PUBLISHED | 6 | 6 |
| 202541121382 A | UTILITY | PUBLISHED | 8 | 4 |
| 202541122891 A | UTILITY | PUBLISHED | 6 | 2 |
| 202541121383 A | UTILITY | PUBLISHED | 7 | 3 |
| 202541123828 A | UTILITY | PUBLISHED | 6 | 6 |
| 484051-001 | DESIGN | GRANTED | 5 | 1 |

## Utility / Design Counts

7 Utility; 2 Design.

## Inventor Matching

Names, source order and source department/external classification are retained verbatim. Exact canonical and approved strong variants are used first. Explicit employee-ID mappings supplied in this verified specification are used only when the existing canonical Master identity agrees; these mappings are reported as SOURCE_EMPLOYEE_ID_VERIFIED, without changing Faculty names or aliases. No fuzzy matching or new Faculty records.

### 202641060300 A

- Mr. B Raja Gopal Reddy → Mr. B. Raja Gopal Reddy → VCE801 (STRONG_VARIANT)
- Mr. Nakka Srinivas → Dr. N. Srinivas → VCE087 (STRONG_VARIANT)
- Mr. A Ananda Kumar → Mr. A. Ananda Kumar → VCE1009 (STRONG_VARIANT)
- Dr. Anuradha Devi Tellapati → Dr. T. Anuradha Devi → VCE1011 (SOURCE_EMPLOYEE_ID_VERIFIED)
- Ms. Puligilla Swetha → CURRENT_DEPARTMENT_UNMATCHED
- Ms. Fatima Unnisa → Ms. Fatima Unnisa → VCE1199 (STRONG_VARIANT)

### 202641060303 A

- Ms. D Revathi → Ms. D. Revathi → VCE792 (STRONG_VARIANT)
- Dr. K Murugaperumal → Dr. Muruga Perumal → VCE1496 (SOURCE_EMPLOYEE_ID_VERIFIED)
- Mr. Adiraju Ramakrishna → Mr. A. Rama Krishna → VCE306 (SOURCE_EMPLOYEE_ID_VERIFIED)
- Ms. Indirarani Guntu → Ms. G. Indirarani → VCE1430 (SOURCE_EMPLOYEE_ID_VERIFIED)
- Dr. Patil Mounica → Dr. Patil Mounica → VCE967 (CANONICAL)
- Mr. Bukya Mohan → Mr. B. Mohan → VCE1074 (SOURCE_EMPLOYEE_ID_VERIFIED)

### 483689-001

- Dr. Patil Mounica → Dr. Patil Mounica → VCE967 (CANONICAL)

### 202541124572 A

- Mr. N. Srinivas → Dr. N. Srinivas → VCE087 (STRONG_VARIANT)
- Dr. S. Ravivarman → Dr. S. Ravivarman → VCE1127 (STRONG_VARIANT)
- Dr. N. Karuppiah → Dr. N. Karuppiah → VCE1172 (STRONG_VARIANT)
- Dr. T. Anuradha Devi → Dr. T. Anuradha Devi → VCE1011 (STRONG_VARIANT)
- Mr. B. Rajagopal Reddy → Mr. B. Raja Gopal Reddy → VCE801 (SOURCE_EMPLOYEE_ID_VERIFIED)
- Dr. Patil Mounica → Dr. Patil Mounica → VCE967 (CANONICAL)

### 202541121382 A

- Dr. Murugaperumal → Dr. Muruga Perumal → VCE1496 (SOURCE_EMPLOYEE_ID_VERIFIED)
- Dr. P Mounica → Dr. Patil Mounica → VCE967 (SOURCE_EMPLOYEE_ID_VERIFIED)
- K Haleema → Ms. K Haleema → VCE1219 (CANONICAL)
- Dr. Venkata Ramana → CURRENT_DEPARTMENT_UNMATCHED
- Bandi Balakrishna → Mr. B. Balakrishna → VCE1837 (SOURCE_EMPLOYEE_ID_VERIFIED)

### 202541122891 A

- S. Vinod Reddy → Mr. S. Vinod Reddy → VCE1422 (STRONG_VARIANT)
- Bandi Balakrishna → Mr. B. Balakrishna → VCE1837 (SOURCE_EMPLOYEE_ID_VERIFIED)

### 202541121383 A

- S. Vinod Reddy → Mr. S. Vinod Reddy → VCE1422 (STRONG_VARIANT)
- Dr. N. Karuppaiah → Dr. N. Karuppiah → VCE1172 (SOURCE_EMPLOYEE_ID_VERIFIED)
- B. Raj Gopal Reddy → Mr. B. Raja Gopal Reddy → VCE801 (SOURCE_EMPLOYEE_ID_VERIFIED)

### 202541123828 A

- Dr. Patil Mounica → Dr. Patil Mounica → VCE967 (CANONICAL)
- Mr. B. Rajagopal Reddy → Mr. B. Raja Gopal Reddy → VCE801 (SOURCE_EMPLOYEE_ID_VERIFIED)
- Dr. T. Anuradha Devi → Dr. T. Anuradha Devi → VCE1011 (STRONG_VARIANT)
- Mr. B. Mohan → Mr. B. Mohan → VCE1074 (STRONG_VARIANT)
- Dr. S. Ravivarman → Dr. S. Ravivarman → VCE1127 (STRONG_VARIANT)
- Dr. N. Karuppiah → Dr. N. Karuppiah → VCE1172 (STRONG_VARIANT)

### 484051-001

- Dr. T Anuradha Devi → Dr. T. Anuradha Devi → VCE1011 (STRONG_VARIANT)

## Multiple Claimants

34 Faculty claim relationships. Per-patent claimant counts are listed above. Each Faculty receives one inventor and one claimed attribution per patent. One patent remains one department record.

## Unmatched Department Inventors

- Ms. Puligilla Swetha (202641060300 A): no approved match to G. Swetha/VCE1546.
- Dr. Venkata Ramana (202541121382 A): no verified Faculty Master match.

K Haleema legitimately matches existing VCE1219. Unmatched names persist as UNKNOWN with CURRENT_DEPARTMENT scope; the API/UI explicitly labels CURRENT_DEPARTMENT_UNMATCHED. They receive no Faculty claim or Faculty KPI.

## External Inventors

19 source external/other rows remain EXTERNAL_PERSON, with affiliation scope UNKNOWN because no organization is supplied. No fictitious affiliation is added. They cannot claim. The source EXTERNAL classification of S Vinod Reddy on 202541121382 A is preserved despite department classification on other patents.

- 483689-001: Dr. C. S. Boopathi; Dr. K. Sridharan; Dr. K. Srinivasarao; Mr. N. Naveen Kumar
- 202541121382 A: Mandepudi Rohith; K Shiva Bhargavi; S Vinod Reddy
- 202541122891 A: M. MouryaSree; K. Manisha; B. ManishGoud; C. Shivanandh
- 202541121383 A: G. Shruthi; M. Jyothi; K. Charan Chandra; T. Saikumar
- 484051-001: Dr. B. Kiran Kumar; Mr. Sangi Narasimhulu; Dr. Vijendra Pratap Singh; Dr. Sushma Jaiswal

## Existing / Duplicate Patents

Initial import: 9 inserted, 0 existing. Actual second run: 0 inserted, 9 existing skipped after verifying source fields, ordered inventors and claims agree. Duplicate normalization reuses existing identifier logic. Conflicting existing fields/relationships stop for manual reconciliation. Display identifiers retain spaces and design hyphens.

## Lifecycle Status

8 PUBLISHED and 1 GRANTED (484051-001). All 9 source publication dates and the sole grant date are preserved. All filing dates remain null. Publication/grant identifier fields are left null; original Patent Number is stored in the existing generic application_number field with provenance. Patent office is explicitly Not specified in source; country remains null. No evidence was fabricated.

## Dashboard Counts

CY 2026 inclusive range: Unique patents 9; Filed 0; Published 8; Granted 1; confirmed Faculty inventors 16; Faculty claim relationships 34. The ninth publication event is 16 December 2025. Department totals deduplicate patent IDs across all events in the selected range. Faculty inventor/claim attribution uses the same event range. Lifecycle columns use their own dates only. Monthly/yearly activity charts deduplicate each patent within a bucket; the same patent can appear in different event months without becoming a second department record.

Live Patents Overview, Research Overview, Faculty Research Contribution and all 16 contributing Faculty detail payloads agree. Source totals: 55 inventors = 36 department (34 matched, 2 unmatched) + 19 external/other. All pre-existing non-patent tables retain their exact values; 325 Publications, 28 Books/Chapters and 20 Faculty remain. See `validation.json` and `migration-audit.json`.

## Tests

Relevant backend regression checks: 44 passed. Frontend unit tests: 49 passed. Browser patent checks: 2 passed, including simultaneous Faculty checkbox claims and event-date drilldowns. Full backend suite: 268 passed. Live browser smoke verified Patents Overview, Research Overview, Faculty Research Contribution and the Patil Mounica details modal without browser errors.

## Backend Build

Python compile check passes. Migration, foreign-key and SQLite integrity checks pass. Backend serves the updated live database.

## Frontend Build

Production Next.js build and TypeScript type-check pass.

View: http://127.0.0.1:3000/patents?from_date=2026-01-01&to_date=2026-12-31
