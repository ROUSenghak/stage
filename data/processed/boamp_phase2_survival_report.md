# BOAMP-only Phase 2 Handoff Dataset

This file is the official BOAMP-only modeling handoff for Phase 2.
It is derived from the notebook renewal-linking output and contains one row
per eligible APPEL_OFFRE notice.

## Composition
| Metric | Value |
|--------|-------|
| Contracts | 1100 |
| Events (plausible renewals) | 705 (64.09%) |
| Right-censored | 395 (35.91%) |

## Variable semantics
- `event = 1`: a plausible renewal link was found under the BOAMP-only algorithm.
- `event = 0`: no renewal link was observed under the algorithm before study end.
- `renewal_duration_months`: observed gap for linked contracts only.
- `censoring_duration_months`: observed time from start date to study end for censored contracts only.

## By category
| category_label | n | events | event_rate_% |
|----------------|---|--------|--------------|
| IT Services & Consulting | 312 | 212 | 67.95 |
| Software & Applications | 209 | 149 | 71.29 |
| Telecom & Networks | 204 | 124 | 60.78 |
| Cybersecurity | 121 | 75 | 61.98 |
| Unknown | 108 | 60 | 55.56 |
| Digital Workplace & Collaboration | 45 | 30 | 66.67 |
| Data & AI | 34 | 13 | 38.24 |
| IT Maintenance & Support | 22 | 15 | 68.18 |
| IT Hardware & Equipment | 21 | 10 | 47.62 |
| Cloud & Infrastructure | 19 | 13 | 68.42 |
| GIS & Mapping | 5 | 4 | 80.0 |