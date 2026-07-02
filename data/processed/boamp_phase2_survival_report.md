# BOAMP-only Phase 2 Handoff Dataset

This file is the official BOAMP-only modeling handoff for Phase 2.
It is derived from the notebook renewal-linking output and contains one row
per eligible APPEL_OFFRE notice.

## Composition
| Metric | Value |
|--------|-------|
| Contracts | 1210 |
| Events (plausible renewals) | 665 (54.96%) |
| Right-censored | 545 (45.04%) |

## Variable semantics
- `event = 1`: a plausible renewal link was found under the BOAMP-only algorithm.
- `event = 0`: no renewal link was observed under the algorithm before study end.
- `renewal_duration_months`: observed gap for linked contracts only.
- `censoring_duration_months`: observed time from start date to study end for censored contracts only.

## By category
| category_label | n | events | event_rate_% |
|----------------|---|--------|--------------|
| IT Services & Consulting | 344 | 208 | 60.47 |
| Software & Applications | 223 | 140 | 62.78 |
| Telecom & Networks | 223 | 116 | 52.02 |
| Cybersecurity | 136 | 73 | 53.68 |
| Unknown | 115 | 49 | 42.61 |
| Digital Workplace & Collaboration | 51 | 32 | 62.75 |
| Data & AI | 40 | 12 | 30.0 |
| IT Hardware & Equipment | 26 | 9 | 34.62 |
| Cloud & Infrastructure | 22 | 11 | 50.0 |
| IT Maintenance & Support | 22 | 11 | 50.0 |
| GIS & Mapping | 8 | 4 | 50.0 |