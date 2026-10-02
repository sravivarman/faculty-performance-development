# Historical journal import reconciliation

Database: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\faculty.db`
Backup: `C:\Users\silic\Documents\GitHub\faculty-performance-development\data\backups\pre_journal_import_20261002_111828.db`
Source: `F:\Downloads\Journals.xlsx` — Journal
Source SHA256: `bdf676203e5aa0bb9fd1ecbd9af7ce9e6ebd5225e90a484a4ae12484b34b493d`

All 138 rows are accounted for; 137 were eligible, with Archana Chittari excluded.

| Status | Rows |
|---|---:|
| IMPORTED | 125 |
| INVALID_DOI | 7 |
| CLAIMANT_NOT_IN_DOI_AUTHORS | 3 |
| DOI_FETCH_FAILED | 2 |
| SKIPPED_UNRESOLVED_CLAIMANT | 1 |

## Remaining review rows

| Excel row | Claimant | Status | Details |
|---:|---|---|---|
| 12 | Praveen Kumar Balachandran | INVALID_DOI | Enter a valid DOI, for example 10.1234/example.123 |
| 15 | Praveen Kumar Balachandran | INVALID_DOI | Enter a valid DOI, for example 10.1234/example.123 |
| 18 | Praveen Kumar Balachandran | INVALID_DOI | Enter a valid DOI, for example 10.1234/example.123 |
| 27 | Praveen Kumar Balachandran | INVALID_DOI | Enter a valid DOI, for example 10.1234/example.123 |
| 47 | T. Anuradha Devi | INVALID_DOI | Missing DOI |
| 48 | Praveen Kumar Balachandran | CLAIMANT_NOT_IN_DOI_AUTHORS | CLAIMANT_NOT_IN_DOI_AUTHORS: expected exactly one conservative author match; found 0; DOI author names: P. Balachandran , G. Kalpana , V. Babyshalini , K. Srilakshmi , S. Singh |
| 77 | Praveen Kumar B | DOI_FETCH_FAILED | DOI not found in Crossref. Retry or continue with manual entry. HTTP 404 |
| 86 | Archana Chittari | SKIPPED_UNRESOLVED_CLAIMANT | Archana Chittari — Excel row 86 — not imported |
| 95 | Praveen Kumar Balachandran | CLAIMANT_NOT_IN_DOI_AUTHORS | CLAIMANT_NOT_IN_DOI_AUTHORS: expected exactly one conservative author match; found 0; DOI author names:  |
| 96 | Karuppiah Natarajan | CLAIMANT_NOT_IN_DOI_AUTHORS | CLAIMANT_NOT_IN_DOI_AUTHORS: expected exactly one conservative author match; found 0; DOI author names:  |
| 128 | S. Ravivarman | DOI_FETCH_FAILED | DOI not found in Crossref. Retry or continue with manual entry. HTTP 404 |
| 137 | N. Srinivas | INVALID_DOI | Enter a valid DOI, for example 10.1234/example.123 |
| 138 | S. Ravivarman | INVALID_DOI | Enter a valid DOI, for example 10.1234/example.123 |

## Integrity and KPI checks

SQLite integrity: ok; foreign-key violations: 0; normalized DOI duplicates: 0.
Each imported publication has exactly one claimant who is an internal DOI author. All original records were preserved.
Excel indexing, impact factors, quartiles, and reconciled claimants match the stored imported records.
Imported publications and unique imported DOIs: 125.
Sum of faculty claimed counts: 125.
Total database publications and unique DOIs (includes original records): 129.
Indexing totals: {'SCI': 62, 'SCIE': 29, 'SCOPUS': 29, 'ESCI': 8}. Multi-index publications appear in each supported category.
Quartile totals: {'Q1': 42, 'Q2': 54, 'Q4': 15, 'Q3': 14}.
With student authors: 0; with multiple faculty authors: 8.
Excel calendar date fallback used: 29 publications; recorded in row warnings.
Unmapped DOI authors remain UNKNOWN. No faculty/student/evidence records were created.

## Faculty claimant summary

| Employee ID | Faculty | Imported claimed publications |
|---|---|---:|
| VCE1476 | B Praveen Kumar | 72 |
| VCE967 | Patil Mounica | 5 |
| VCE1127 | Dr. S. Ravivarman | 8 |
| VCE640 | Dr. H.S. Jain | 1 |
| VCE1172 | Dr. N. Karuppiah | 8 |
| VCE085 | Dr. Md. Asif | 1 |
| VCE1496 | Dr. Muruga Perumal | 15 |
| VCE1011 | Dr. T. Anuradha Devi | 8 |
| VCE087 | Dr. N. Srinivas | 2 |
| VCE801 | Mr. B. Raja Gopal Reddy | 0 |
| VCE306 | Mr. A. Rama Krishna | 3 |
| VCE1009 | Mr. A. Ananda Kumar | 2 |
| VCE1430 | Ms. G. Indirarani | 0 |
| VCE1074 | Mr. B. Mohan | 0 |
| VCE1199 | Ms. Fatima Unnisa | 0 |
| VCE1422 | Mr. S. Vinod Reddy | 0 |
| VCE792 | Ms. D. Revathi | 0 |
| VCE1837 | Mr. B. Balakrishna | 0 |
| VCE1546 | Ms. G. Swetha | 0 |
