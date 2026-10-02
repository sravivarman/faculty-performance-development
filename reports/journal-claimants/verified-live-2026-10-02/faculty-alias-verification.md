# Live Faculty Alias Verification

The approved aliases were already present in the live SQLite database before this diagnostic run. All 18 supplied spellings resolve uniquely as STRONG_VARIANT. No aliases needed inserting; no publications were imported.

Generated at (UTC): `2026-10-02T05:41:06.957623+00:00`

## Database Paths

- application: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\faculty.db`
- faculty_seed: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\faculty.db`
- faculty_alias_update: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\faculty.db`
- journal_reconciliation: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\faculty.db`

Paths read from PRAGMA database_list on the actual connections. The app path is returned by its running /health endpoint.

## Faculty Variant Verification

### VCE1009 — Mr. A. Ananda Kumar

Active: True · Stored variant count: 5

- `A. Ananda Kumar` → `a ananda kumar` · STRONG
- `Ananda Kumar A` → `ananda kumar a` · STRONG
- `A. Anandakumar` → `a anandakumar` · STRONG
- `Anandakumar A` → `anandakumar a` · STRONG
- `Annavarapu Ananda Kumar` → `annavarapu ananda kumar` · STRONG
### VCE640 — Dr. H.S. Jain

Active: True · Stored variant count: 3

- `H.S. Jain` → `hs jain` · STRONG
- `Jain H.S.` → `jain hs` · STRONG
- `Hari Shankar Jain` → `hari shankar jain` · STRONG
### VCE1172 — Dr. N. Karuppiah

Active: True · Stored variant count: 4

- `N. Karuppiah` → `n karuppiah` · STRONG
- `Karuppiah N` → `karuppiah n` · STRONG
- `Karuppiah Natarajan` → `karuppiah natarajan` · STRONG
- `Natarajan Karuppiah` → `natarajan karuppiah` · STRONG
### VCE087 — Dr. N. Srinivas

Active: True · Stored variant count: 4

- `N. Srinivas` → `n srinivas` · STRONG
- `Srinivas N` → `srinivas n` · STRONG
- `NAKKA SRINIVAS` → `nakka srinivas` · STRONG
- `Srinivas Nakka` → `srinivas nakka` · STRONG
### VCE1011 — Dr. T. Anuradha Devi

Active: True · Stored variant count: 4

- `T. Anuradha Devi` → `t anuradha devi` · STRONG
- `Anuradha Devi T` → `anuradha devi t` · STRONG
- `T. Anuradha` → `t anuradha` · STRONG
- `Tellapati Anuradha Devi` → `tellapati anuradha devi` · STRONG
### VCE1496 — Dr. Muruga Perumal

Active: True · Stored variant count: 7

- `Muruga Perumal` → `muruga perumal` · STRONG
- `M. Perumal` → `m perumal` · WEAK
- `Perumal Muruga` → `perumal muruga` · STRONG
- `Murugaperumal Krishnamoorthy` → `murugaperumal krishnamoorthy` · STRONG
- `Muruagapermual Krishnamoorthy` → `muruagapermual krishnamoorthy` · STRONG
- `Murugaperumal Krisnamoorthy` → `murugaperumal krisnamoorthy` · STRONG
- `Murugaperunal Krishnamoorthy` → `murugaperunal krishnamoorthy` · STRONG
### VCE1476 — B Praveen Kumar

Active: True · Stored variant count: 5

- `Praveen Kumar Balachandran` → `praveen kumar balachandran` · STRONG
- `Praven Kumar Balachandran` → `praven kumar balachandran` · STRONG
- `Balachandran Praveen Kumar` → `balachandran praveen kumar` · STRONG
- `Balachandran, P. K` → `balachandran pk` · STRONG
- `Praveen Kumar B` → `praveen kumar b` · STRONG

## Matching Verification

All expected aliases exist by normalized key. Case/punctuation equivalents deliberately share one stored variant.

| Source string | Normalized value | Employee ID | Matched faculty | Match source | Stored spelling |
| --- | --- | --- | --- | --- | --- |
| Annavarapu Ananda Kumar | annavarapu ananda kumar | VCE1009 | Mr. A. Ananda Kumar | STRONG_VARIANT | Annavarapu Ananda Kumar |
| Hari Shankar Jain | hari shankar jain | VCE640 | Dr. H.S. Jain | STRONG_VARIANT | Hari Shankar Jain |
| Karuppiah Natarajan | karuppiah natarajan | VCE1172 | Dr. N. Karuppiah | STRONG_VARIANT | Karuppiah Natarajan |
| Natarajan Karuppiah | natarajan karuppiah | VCE1172 | Dr. N. Karuppiah | STRONG_VARIANT | Natarajan Karuppiah |
| NAKKA SRINIVAS | nakka srinivas | VCE087 | Dr. N. Srinivas | STRONG_VARIANT | NAKKA SRINIVAS |
| Nakka Srinivas | nakka srinivas | VCE087 | Dr. N. Srinivas | STRONG_VARIANT | NAKKA SRINIVAS |
| Srinivas Nakka | srinivas nakka | VCE087 | Dr. N. Srinivas | STRONG_VARIANT | Srinivas Nakka |
| Tellapati Anuradha Devi | tellapati anuradha devi | VCE1011 | Dr. T. Anuradha Devi | STRONG_VARIANT | Tellapati Anuradha Devi |
| Murugaperumal Krishnamoorthy | murugaperumal krishnamoorthy | VCE1496 | Dr. Muruga Perumal | STRONG_VARIANT | Murugaperumal Krishnamoorthy |
| Muruagapermual Krishnamoorthy | muruagapermual krishnamoorthy | VCE1496 | Dr. Muruga Perumal | STRONG_VARIANT | Muruagapermual Krishnamoorthy |
| Murugaperumal Krisnamoorthy | murugaperumal krisnamoorthy | VCE1496 | Dr. Muruga Perumal | STRONG_VARIANT | Murugaperumal Krisnamoorthy |
| Murugaperunal Krishnamoorthy | murugaperunal krishnamoorthy | VCE1496 | Dr. Muruga Perumal | STRONG_VARIANT | Murugaperunal Krishnamoorthy |
| Praveen Kumar Balachandran | praveen kumar balachandran | VCE1476 | B Praveen Kumar | STRONG_VARIANT | Praveen Kumar Balachandran |
| Praven Kumar Balachandran | praven kumar balachandran | VCE1476 | B Praveen Kumar | STRONG_VARIANT | Praven Kumar Balachandran |
| Balachandran Praveen Kumar | balachandran praveen kumar | VCE1476 | B Praveen Kumar | STRONG_VARIANT | Balachandran Praveen Kumar |
| Balachandran, P. K | balachandran pk | VCE1476 | B Praveen Kumar | STRONG_VARIANT | Balachandran, P. K |
| Balachandran, P. K. | balachandran pk | VCE1476 | B Praveen Kumar | STRONG_VARIANT | Balachandran, P. K |
| Praveen Kumar B | praveen kumar b | VCE1476 | B Praveen Kumar | STRONG_VARIANT | Praveen Kumar B |

## Normalization Collision Check

No normalized approved variant belongs to more than one faculty, including inactive faculty and canonical-name conflicts.

## Reconciliation Summary

| Measure | Count |
| --- | ---: |
| Faculty Master Count | 19 |
| Faculty Name Variant Count | 64 |
| Total Journal Rows | 138 |
| Unique Excel Claimant Values | 32 |
| Canonical Matches | 9 |
| Strong Variant Matches | 22 |
| Weak Variant Matches | 0 |
| Unmatched Values | 1 |
| Ambiguous Values | 0 |
| Rows Requiring Review | 1 |
| Blank Claimant Rows | 0 |
| Missing Title Rows | 0 |
| Grouped Row Total | 138 |

Matched rows: 137/138. Canonical: 26 rows; strong variants: 111 rows. Every original Excel row (2–139) is represented exactly once.

## Remaining Unresolved

- Archana Chittari: UNMATCHED · 1 row(s) · Excel row(s): 86

The original workbook and all publication, author, evidence, student, patent and book rows are unchanged.

The file identified by the user, F:\Downloads\Journals.xlsx, is the original source workbook. It contains only the Journal sheet and has intentionally not been rewritten. Updated reconciliation results are separate reports in this directory. The previously saved report already had these same updated totals; no database mismatch or alias-matching defect was reproduced. Open claimant-reconciliation.csv for the regenerated Excel-readable results, or this verification report for the database audit.
