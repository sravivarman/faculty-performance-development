# Research Records dashboard rollout

## Research Overview

Production home: http://127.0.0.1:3000/. The approved layout replaces the former overview. The separate `/research/design-preview` route and duplicate preview components have been removed.

## Research Activity KPIs

Eight cards: Journals, Conferences, Patents, Books / Chapters, FDP / Workshop / Seminar, Certifications, Research Proposals and Consultancy. Desktop uses four columns and two rows. Module drill-downs retain explicit inclusive dates. Unimplemented modules show **Not configured** and link to their dashboard shells.

## Research Activity Trend

Full-width Apache ECharts chart with Monthly, Quarterly, Half Yearly and Yearly controls. Months, quarters and calendar halves retain zero periods. Calendar years come from recorded, eligible activity; the current year is selected when it has data, otherwise the latest available year. Yearly mode disables the single-year selector. Global date boundaries constrain every bucket, including historical yearly buckets. Patent activity uses filing date; publication and book activity use publication date. The legend toggles configured series locally.

## Publications 2 × 2 Analytics

Publication filters and summary, Publications by Type, Indexing Distribution and Quartile Distribution occupy exactly four desktop tiles. Publication Type, Indexing, Classification and Quartile affect publication analytics independently of the research KPIs. Indexing categories can overlap; totals are never derived by adding indexing counts.

## Faculty Research Contribution

Full-width searchable, sortable Tremor Raw table. Journal and Conference columns count unique authored records. Claims, authorship and patent inventorship retain their separate meanings. There is no composite score or invented ranking.

## Faculty Research Details Modal

One reusable, on-demand modal serves all four configured dashboards. It shows Faculty Master identity, employee ID, designation and the selected range. Tabs contain Summary, Publications, Patents and Books / Chapters. Publication rows include claim status, indexing, quartile and classification. Patent rows include application number and lifecycle dates. Titles open existing record detail pages with the selected dates. Unconfigured modules remain **Not configured** in the summary. Escape and Close dismiss the native dialog; no record-editing UI is duplicated inside it.

## Publications Overview

http://127.0.0.1:3000/publications

Shared dashboard UI, primary/indexing/quality KPI cards, five ECharts analytics, faculty contribution table and shared faculty modal. Existing filters, recent publications, attention indicators, month drill-downs and filtered publication lists remain available. DOI, multiple DOI, BibTeX, manual entry, editing and evidence workflows remain intact.

## Patents Overview

http://127.0.0.1:3000/patents

Eight primary KPIs, lifecycle trend, lifecycle stage distribution, collaboration distribution and activity by faculty. Claim and inventor counts are separate. Event counts use their respective filing/publication/grant dates. Faculty names open the shared modal; student involvement and record drill-downs remain available.

## Books / Chapters Overview

http://127.0.0.1:3000/books

Seven primary KPIs, Books vs Chapters, publication trend and a classification placeholder. International/National and Classification Distribution show **Not configured** because the current model has no classification field. Additional collaboration/authorship indicators remain available. Eligible whole-book editors contribute to Total Works and the profile without becoming authored works automatically.

## FDP / Workshop / Seminar Overview

http://127.0.0.1:3000/fdp — consistent dashboard shell with category cards, chart placeholders and faculty section. No backend data is fabricated or fetched for the missing module.

## Certifications Overview

http://127.0.0.1:3000/certifications — consistent shell for Total Certifications, Faculty Certified, NPTEL, Industry and Other, plus chart/table placeholders.

## Research Proposals Overview

http://127.0.0.1:3000/proposals — consistent shell for statuses, Funds Sanctioned, contributors and proposed charts. Financial values remain unavailable, not zero.

## Consultancy Overview

http://127.0.0.1:3000/consultancy — consistent project/revenue/status shell. Financial formatting supports Indian rupees; unsupported revenue values are not invented or mixed with count axes.

## Shared Components

Tremor Raw Card and Table components retain source attribution and their license in `components/dashboard/TREMOR-LICENSE`. UI primitives are adapted from the official [Card](https://www.tremor.so/docs/ui/card) and [Table](https://www.tremor.so/docs/ui/table) sources, using prefixed Tailwind utilities without Preflight. This preserves the React 19 setup without forcing the legacy React-18-only Tremor package.

Shared components cover page headers, date ranges, KPI grids, sections/tiles, filters, empty/error states, attention panels, sortable faculty tables, faculty profiles and charts. A single lazy-loaded SVG ECharts wrapper handles theme, safe tooltips, resize, loading, empty/error states, click callbacks and disposal. Old HTML bar/trend visualizations are replaced by ECharts; keyboard drill-down controls remain alongside charts.

## Backend Aggregation

Existing `/research/overview` and `/publication-dashboard` reporting APIs remain compatible. New read-only `/patent-dashboard`, `/book-dashboard` and `/research/faculty/{id}` payloads reuse existing module counting/filtering services. Trend month boundaries are supplied by the server. Research calendar/granularity aggregation remains centralized in the existing research reporting service. No business-data or schema migration was introduced.

## Drill-down

KPI, table and chart interactions preserve explicit dates and applicable module, faculty, publication type, indexing, classification, quartile and lifecycle filters. Monthly drill-down bounds come from backend buckets. Module URL state survives reloads and returning from book record details. People KPIs remain distinct from activity-record counts; corresponding lists identify their involved records.

## Responsive Design

Desktop, tablet and mobile are checked. KPI and analytics grids reflow to two columns and then one; the research trend and faculty table remain full-width. Tables scroll within their containers. ECharts resizing and mobile document overflow are tested. Loading states preserve chart dimensions and existing table geometry during updates; API/chart errors remain localized.

## Tests

235 backend tests and 39 frontend unit tests passed. The full 16-test browser suite passed, covering existing entry/evidence/editing/master flows as well as dashboard layout, all trend granularities, dynamic year selection, the faculty modal, distinct counting, actual ECharts click drill-down, date preservation, error isolation and responsive behavior. Follow-up dashboard/module checks cover the final shared loading/theme changes.

## Production Build

Frontend TypeScript check and the Next.js production build pass. No lint command is configured in the project. The final build includes all eight production dashboards and excludes the removed preview route.

## Remaining Modules / Limitations

FDP / Workshop / Seminar, Certifications, Research Proposals and Consultancy still require real backend modules before reporting values or records can appear. Books classification requires a separately approved business-model change; this redesign adds no such field. Faculty profiles use confirmed master mappings and current stored data, without inferring unknown authors or importing publications.
