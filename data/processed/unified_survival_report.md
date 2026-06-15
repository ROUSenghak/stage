# Task 8 – Unified Survival Dataset

## Composition
| Source | Contracts | Events | Event rate |
|--------|-----------|--------|------------|
| DECP (2018–2024) | 3037 | 252 | 8.3% |
| BOAMP (2015–2017) | 475 | 85 | 17.9% |
| **Total** | **3512** | **337** | **9.6%** |

## Why censoring is expected
55% of DECP contracts started in 2022 or later. With typical 48-month
durations, their renewals would fall after the study end (Dec 2024).
Survival analysis handles this correctly via right-censoring — censored
observations are valid data, not missing data.

## Linking methods
- `decp_jaccard`: Jaccard similarity ≥ 0.30, time window ± 6 months (task6).
- `boamp_jaccard`: Jaccard similarity ≥ 0.20, time window ± 12 months (task_boamp_full_survival).
- `none`: no renewal found — contract treated as right-censored at study end.
- `annonce_lie` was used to refine BOAMP start dates (award date > pub date).

## Known limitations
1. BOAMP buyer_key is name-based for ~91% of records (SIRET coverage ~9%).
   Name normalization may split one real buyer into multiple keys.
2. Cross-source deduplication (BOAMP post-2018 vs DECP) is handled by
   excluding BOAMP notices from 2018 onwards. Some pre-2018 DECP records
   may still overlap if DECP backfilling extended before 2018.
3. The event rate (~8%) reflects the observation window, not a data defect.
   For survival modeling, all rows (event=0 and event=1) contribute.