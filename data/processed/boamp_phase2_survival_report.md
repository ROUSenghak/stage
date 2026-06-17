# BOAMP-only Phase 2 Handoff Dataset

This file is the official BOAMP-only modeling handoff for Phase 2.
It is derived from the notebook renewal-linking output and contains one row
per eligible APPEL_OFFRE notice.

## Composition
| Metric | Value |
|--------|-------|
| Contracts | 1100 |
| Events (plausible renewals) | 697 (63.36%) |
| Right-censored | 403 (36.64%) |

## Variable semantics
- `event = 1`: a plausible renewal link was found under the BOAMP-only algorithm.
- `event = 0`: no renewal link was observed under the algorithm before study end.
- `renewal_duration_months`: observed gap for linked contracts only.
- `censoring_duration_months`: observed time from start date to study end for censored contracts only.

## By category
| category_label | n | events | event_rate_% |
|----------------|---|--------|--------------|
| IT Services & Consulting | 312 | 211 | 67.63 |
| Software & Applications | 209 | 148 | 70.81 |
| Telecom & Networks | 204 | 120 | 58.82 |
| Cybersecurity | 121 | 76 | 62.81 |
| Unknown | 108 | 58 | 53.7 |
| Digital Workplace & Collaboration | 45 | 29 | 64.44 |
| Data & AI | 34 | 14 | 41.18 |
| IT Maintenance & Support | 22 | 14 | 63.64 |
| IT Hardware & Equipment | 21 | 10 | 47.62 |
| Cloud & Infrastructure | 19 | 13 | 68.42 |
| GIS & Mapping | 5 | 4 | 80.0 |