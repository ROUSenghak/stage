# BOAMP-only Survival Dataset

## Composition
| Metric | Value |
|--------|-------|
| Survival units (APPEL_OFFRE) | 1933 |
| Linked renewals (events) | 146 (7.6%) |
| Right-censored | 1787 (92.4%) |
| Median observed duration | 48.9 months |

## Linking parameters
- Time window: declared duration ± 6.0 months (default 48.0 months when missing)
- Minimum Jaccard similarity: 0.2
- Scoring: 0.7 × text_similarity + 0.3 × time_fit
- Start date: award date (via annonce_lie) when available, publication date otherwise

## By CPV division
| cpv_div2 | n | events | event_rate_% |
|----------|---|--------|--------------|
| 15 | 1 | 0 | 0.0 |
| 18 | 16 | 0 | 0.0 |
| 22 | 3 | 0 | 0.0 |
| 30 | 36 | 1 | 2.8 |
| 31 | 6 | 0 | 0.0 |
| 32 | 300 | 18 | 6.0 |
| 33 | 1 | 0 | 0.0 |
| 34 | 5 | 0 | 0.0 |
| 35 | 128 | 6 | 4.7 |
| 37 | 4 | 1 | 25.0 |
| 38 | 7 | 0 | 0.0 |
| 39 | 23 | 3 | 13.0 |
| 42 | 5 | 0 | 0.0 |
| 43 | 2 | 0 | 0.0 |
| 44 | 13 | 2 | 15.4 |
| 45 | 87 | 0 | 0.0 |
| 48 | 372 | 27 | 7.3 |
| 50 | 21 | 0 | 0.0 |
| 51 | 2 | 0 | 0.0 |
| 64 | 15 | 1 | 6.7 |
| 66 | 1 | 0 | 0.0 |
| 71 | 13 | 2 | 15.4 |
| 72 | 772 | 83 | 10.8 |
| 75 | 4 | 0 | 0.0 |
| 79 | 23 | 1 | 4.3 |
| 90 | 5 | 0 | 0.0 |
| 92 | 4 | 0 | 0.0 |
| 98 | 2 | 0 | 0.0 |

## By category
| category_label | n | events | event_rate_% |
|----------------|---|--------|--------------|
| IT Services & Consulting | 583 | 62 | 10.6 |
| Software & Applications | 373 | 27 | 7.2 |
| Telecom & Networks | 337 | 19 | 5.6 |
| Cybersecurity | 211 | 15 | 7.1 |
| Unknown | 176 | 6 | 3.4 |
| Digital Workplace & Collaboration | 89 | 5 | 5.6 |
| Data & AI | 54 | 2 | 3.7 |
| IT Hardware & Equipment | 45 | 1 | 2.2 |
| IT Maintenance & Support | 31 | 6 | 19.4 |
| Cloud & Infrastructure | 25 | 1 | 4.0 |
| GIS & Mapping | 9 | 2 | 22.2 |

## Known limitations
1. buyer_key is name-based for 90%+ of records (SIRET coverage ~9% in BOAMP).
   Name normalization may split one real buyer into multiple keys (e.g. 'Ville de Nantes' vs 'Nantes Metropole').
2. Jaccard linking on short objet strings can produce false positives for
   generic descriptions ('prestations informatiques', 'maintenance informatique').
3. Contracts started in 2021-2024 are almost certainly right-censored: with
   typical 48-month durations, their renewals fall after the 2024-12-31 study end.