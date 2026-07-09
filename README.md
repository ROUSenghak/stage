# BOAMP / Gigalis Current Recurrence Study

This repository now centers on the **current enriched BOAMP dataset** for the Gigalis internship scope: Pays de la Loire digital BOAMP notices. The current study dataset is built under `data/processed/boamp_current/` from raw BOAMP API extracts cached under `data/raw/boamp_current/`.

Events in this project are **proxy recurrences**: identifiable reappearances of similar procurement needs under a documented linkage rule. They are not legally verified renewals, and real BOAMP precision/recall are not directly observed.

## Current Study Snapshot

The current run was executed on branch `boamp_enriched_current_dataset` from starting commit `4847230b1024f49e1a41f8d34e7967acd6688c21`.

| Item | Current value |
|---|---:|
| Study period in downloaded data | 2015-03-02 to 2026-07-09 |
| Retained BOAMP notices | 3,656 |
| APPEL_OFFRE notices | 2,216 |
| Linkage-eligible contracts | 1,661 |
| Selected proxy-event method | M0 balanced |
| Proxy recurrence events | 183 |
| Event rate | 11.0% |
| Censoring date | 2026-07-09 |
| Selected AFT model | LogLogisticAFT |
| Expected 12-month proxy recurrences | 48.4 |

The selected method is recorded in `reports/tables/linkage/final_selected_event_definition_current.csv`. M2 balanced remains a useful benchmark, but in this current run it produced too few events for the event-sufficiency rule, so M0 balanced was selected.

## Main Current Outputs

| Output | Role |
|---|---|
| `data/raw/boamp_current/download_metadata.json` | Download source, extraction date, scope, requested and actual date ranges, counts, warnings |
| `data/processed/boamp_current/boamp_full_clean_enriched.csv` | Current enriched notice-level source of truth |
| `data/processed/boamp_current/boamp_survival_population_base.csv` | Current APPEL_OFFRE analytical population |
| `data/processed/boamp_current/boamp_candidate_pairs_enriched.csv` | Current enriched buyer-key candidate pairs |
| `data/processed/boamp_current/boamp_survival_method_m0_balanced.csv` | Selected current survival input |
| `reports/tables/linkage/method_comparison_current_dataset.csv` | Current M0/M1/M2 method comparison |
| `reports/tables/validation/methodology_tests_summary_current.csv` | Current methodology-test conclusions |
| `reports/tables/survival/operational_risk_scores_current.csv` | Current 12/24-month operational risk scores |
| `reports/tables/survival/live_contract_risk_scores_current.csv` | Current Gigalis-facing live scoring table |
| `reports/current_boamp_recurrence_study_report.pdf` | Current final report |
| `reports/current_source_values_used.csv` | Source trace for reported numbers |
| `reports/tables/audit/final_current_pipeline_audit.csv` | Final current pipeline audit |

## Reproduce The Current Run

Use the project virtual environment:

```bash
.venv/bin/python3 scripts/download_boamp_current.py --start-date 2015-01-01 --end-date 2026-07-09
.venv/bin/python3 scripts/build_boamp_current_enriched.py
MPLCONFIGDIR=/tmp/matplotlib-stage-1 .venv/bin/python3 scripts/build_current_survival_population.py
MPLCONFIGDIR=/tmp/matplotlib-stage-1 .venv/bin/python3 scripts/generate_current_candidate_pairs.py
MPLCONFIGDIR=/tmp/matplotlib-stage-1 .venv/bin/python3 scripts/run_current_linkage_methods.py
MPLCONFIGDIR=/tmp/matplotlib-stage-1 .venv/bin/python3 scripts/run_current_methodology_tests.py
MPLCONFIGDIR=/tmp/matplotlib-stage-1 .venv/bin/python3 scripts/run_current_survival_analysis.py
.venv/bin/python3 scripts/score_live_recurrence_risk_current.py --prediction-date 2026-07-09
.venv/bin/python3 scripts/build_current_report.py
latexmk -pdf -cd reports/current_boamp_recurrence_study_report.tex
.venv/bin/python3 scripts/audit_current_pipeline.py
```

The downloader and enrichment steps use public network services. Raw files and SIREN lookup cache are stored under `data/raw/boamp_current/`.

## Historical Artifacts

Older 2015-2024 outputs remain in the repository for traceability and Git history, but they are not the current study results. Treat files without the `boamp_current` path or `_current` suffix as historical unless a current report explicitly cites them.

## Environment

The current methodology stack is declared in `requirements.txt`. Important packages include `pandas`, `numpy`, `scipy`, `scikit-learn`, `lifelines`, `sentence-transformers`, `rapidfuzz`, `recordlinkage`, `splink`, `xgboost`, `lightgbm`, `datasketch`, `networkx`, `pyarrow`, and `requests`.
