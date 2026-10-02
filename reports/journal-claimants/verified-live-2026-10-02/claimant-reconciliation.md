# Journal claimant reconciliation

Source: `F:\Downloads\Journals.xlsx` · Sheet: `Journal`

SQLite database: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\faculty.db`

Generated at (UTC): `2026-10-02T05:41:06.910809+00:00`

Authors is the departmental claimant field, not the complete publication author list. No publications have been imported.

## Summary

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

Row conservation: **138 grouped rows = 138 nonempty journal rows**.

Weak and ambiguous matches require manual review. Unmatched values remain unresolved; no new faculty are created from Excel names.

## Unique claimant values

| Excel Author Value | Normalized Excel Value | Matched Faculty | Employee ID | Match Source | Number of Excel Rows | Requires Review |
| --- | --- | --- | --- | --- | ---: | --- |
| A. Ramakrishna | a ramakrishna | Mr. A. Rama Krishna | VCE306 | STRONG_VARIANT | 2 | No |
| Annavarapu Ananda Kumar | annavarapu ananda kumar | Mr. A. Ananda Kumar | VCE1009 | STRONG_VARIANT | 2 | No |
| Archana Chittari | archana chittari | — | — | UNMATCHED | 1 | Yes |
| B Praveen Kumar | b praveen kumar | B Praveen Kumar | VCE1476 | CANONICAL | 1 | No |
| B. Praveen Kumar | b praveen kumar | B Praveen Kumar | VCE1476 | CANONICAL | 9 | No |
| Balachandran Praveen Kumar | balachandran praveen kumar | B Praveen Kumar | VCE1476 | STRONG_VARIANT | 1 | No |
| Balachandran, P. K | balachandran pk | B Praveen Kumar | VCE1476 | STRONG_VARIANT | 1 | No |
| Balachandran, P. K. | balachandran pk | B Praveen Kumar | VCE1476 | STRONG_VARIANT | 1 | No |
| Dr. Patil Mounica | patil mounica | Patil Mounica | VCE967 | CANONICAL | 1 | No |
| Hari Shankar Jain | hari shankar jain | Dr. H.S. Jain | VCE640 | STRONG_VARIANT | 1 | No |
| Karuppiah N | karuppiah n | Dr. N. Karuppiah | VCE1172 | STRONG_VARIANT | 1 | No |
| Karuppiah Natarajan | karuppiah natarajan | Dr. N. Karuppiah | VCE1172 | STRONG_VARIANT | 4 | No |
| Md Asif | md asif | Dr. Md. Asif | VCE085 | CANONICAL | 1 | No |
| Muruagapermual Krishnamoorthy | muruagapermual krishnamoorthy | Dr. Muruga Perumal | VCE1496 | STRONG_VARIANT | 1 | No |
| Murugaperumal Krishnamoorthy | murugaperumal krishnamoorthy | Dr. Muruga Perumal | VCE1496 | STRONG_VARIANT | 12 | No |
| Murugaperumal Krisnamoorthy | murugaperumal krisnamoorthy | Dr. Muruga Perumal | VCE1496 | STRONG_VARIANT | 1 | No |
| Murugaperunal Krishnamoorthy | murugaperunal krishnamoorthy | Dr. Muruga Perumal | VCE1496 | STRONG_VARIANT | 1 | No |
| N. Karuppiah | n karuppiah | Dr. N. Karuppiah | VCE1172 | CANONICAL | 1 | No |
| N. Srinivas | n srinivas | Dr. N. Srinivas | VCE087 | CANONICAL | 1 | No |
| NAKKA SRINIVAS | nakka srinivas | Dr. N. Srinivas | VCE087 | STRONG_VARIANT | 1 | No |
| Natarajan Karuppiah | natarajan karuppiah | Dr. N. Karuppiah | VCE1172 | STRONG_VARIANT | 3 | No |
| Patil Mounica | patil mounica | Patil Mounica | VCE967 | CANONICAL | 4 | No |
| Praveen Kumar B | praveen kumar b | B Praveen Kumar | VCE1476 | STRONG_VARIANT | 4 | No |
| Praveen Kumar Balachandran | praveen kumar balachandran | B Praveen Kumar | VCE1476 | STRONG_VARIANT | 61 | No |
| Praven Kumar Balachandran | praven kumar balachandran | B Praveen Kumar | VCE1476 | STRONG_VARIANT | 1 | No |
| Ramakrishna, A | ramakrishna a | Mr. A. Rama Krishna | VCE306 | STRONG_VARIANT | 1 | No |
| Ravivarman Shanmugasundaram | ravivarman shanmugasundaram | Dr. S. Ravivarman | VCE1127 | STRONG_VARIANT | 4 | No |
| Ravivarman, S. | ravivarman s | Dr. S. Ravivarman | VCE1127 | STRONG_VARIANT | 1 | No |
| S. Ravivarman | s ravivarman | Dr. S. Ravivarman | VCE1127 | CANONICAL | 5 | No |
| Srinivas Nakka | srinivas nakka | Dr. N. Srinivas | VCE087 | STRONG_VARIANT | 1 | No |
| T. Anuradha Devi | t anuradha devi | Dr. T. Anuradha Devi | VCE1011 | CANONICAL | 3 | No |
| Tellapati Anuradha Devi | tellapati anuradha devi | Dr. T. Anuradha Devi | VCE1011 | STRONG_VARIANT | 6 | No |
