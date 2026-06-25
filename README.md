# Phase 1 — BOAMP-First Data Exploration and Renewal Linking

This repository documents the Phase 1 BOAMP-first workflow for the Gigalis
predictive-modeling internship. The current official modeling path is
**BOAMP-only**: raw BOAMP acquisition, BOAMP cleaning, BOAMP renewal linking,
and export of one survival-analysis-ready table for Phase 2.

Scope: digital contracts (CPV 48 software, 72 IT services, 32 telecom,
35 security), Pays de la Loire (departments 44/49/53/72/85), 2015–2024.

DECP exploration remains in the repository as documented research and a later
enrichment path, but it is **not part of the current official Phase 2 handoff**.

## Reading guide

- `reports/internship_report.tex`: quick orientation report to scan the internship scope, main tasks, headline results, and where each part of the work sits.
- `reports/phase1_technical_report.tex`: detailed technical reference for the exact data audit, preprocessing, renewal-linking logic, diagnostics, and modeling choices.

## Setup

```bash
pip install -r requirements.txt
```

## Official run order (BOAMP-only)

```bash
# Phase 1 — BOAMP acquisition and profiling
python scripts/task1b_boamp_full_fetch.py    # full BOAMP download (3,181 notices)
python scripts/task2_boamp_profile.py        # BOAMP field profiling + deep-dives
python scripts/task5_duration_analysis.py    # duration-reliability analysis + figures

# Phase 2 — BOAMP cleaning and renewal linking
python scripts/task_boamp_full_clean.py      # apply cleaning to full BOAMP data
python scripts/task_boamp_full_survival.py   # BOAMP scripted baseline (Jaccard)

# Phase 3 — official Phase 2 handoff (from the BOAMP notebooks)
# Run the BOAMP renewal-linking notebook top-to-bottom first:
#   boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb
# Note: the notebook auto-downloads paraphrase-multilingual-MiniLM-L12-v2 (~120 MB)
# from HuggingFace on first run. Internet access required; subsequent runs use
# the local cache at ~/.cache/huggingface/.
python scripts/task9_boamp_phase2_handoff.py
```

The official Phase 2 modeling input is
`data/processed/boamp_phase2_survival.csv`, exported from the BOAMP renewal-linking
notebook output `boamp_renewal_linking_quality/outputs/boamp_renewal_links.csv`.

The original 500-notice sample (`task1_boamp_fetch.py`) is kept for reference
but superseded by the full download.

## Optional exploratory paths

These files remain useful for source comparison and later enrichment, but are
currently out of scope for the official BOAMP-only handoff:

```bash
python scripts/task3_decp_fetch_profile.py   # DECP source exploration
python scripts/task4_compare.py              # BOAMP vs DECP comparison table
python scripts/task7_week2_cleaning.py       # shared cleaning functions + DECP cleaning
python scripts/task6_renewal_linking.py      # DECP renewal-linking baseline
python scripts/task8_unified_survival.py     # mixed BOAMP + DECP survival dataset
```

## Outputs

| Path | Content |
|---|---|
| `data/raw/boamp_full/` | raw full BOAMP API pages (JSON, verbatim) |
| `data/raw/boamp_sample/` | original 500-notice sample pages (reference only) |
| `data/processed/boamp_full_flat.csv` | **3,181 BOAMP notices, flattened** (primary) |
| `data/processed/boamp_full_clean.csv` | **3,181 notices, cleaned** — buyer keys, amounts, durations, taxonomy |
| `data/processed/boamp_phase2_survival.csv` | **official BOAMP-only Phase 2 handoff** — one row per eligible AO with event/censoring |
| `data/processed/boamp_phase2_survival_report.md` | BOAMP-only handoff dataset report |
| `data/processed/boamp_full_survival.csv` | **1,933 APPEL_OFFRE survival records** — event/censoring, ±12 month window |
| `data/processed/boamp_full_survival_report.md` | survival dataset composition report |
| `data/processed/boamp_sample_flat.csv` | 500-notice BOAMP sample (reference only) |
| `boamp_renewal_linking_quality/outputs/boamp_renewal_links.csv` | **official BOAMP renewal-linking notebook output** — 1,100 eligible AO, 705 linked |
| `boamp_renewal_linking_quality/outputs/boamp_linking_stats.csv` | linking-rate summary for the BOAMP-only final method |
| `boamp_renewal_linking_quality/outputs/boamp_bias_report.csv` | bias/failure-reason report for the BOAMP-only final method |
| `boamp_renewal_linking_quality/outputs/boamp_renewal_candidates.csv` | candidate-pair table before best-match selection |
| `data/raw/decp/` | DECP download — decp.parquet (git-ignored, re-downloadable; exploratory only) |
| `data/processed/decp_sample_flat.csv` | filtered DECP contracts (3,039) |
| `data/processed/decp_clean.csv` | DECP with buyer keys, cleaned amounts/durations, taxonomy tags |
| `data/processed/decp_renewal_links.csv` | DECP contracts with linked renewal event/censoring durations |
| `data/processed/unified_survival.csv` | combined BOAMP+DECP survival records (exploratory only) |
| `data/processed/unified_survival_report.md` | unified dataset composition report |
| `data/processed/taxonomy.csv` | 10-category tech taxonomy (CPV + keywords) |
| `data/processed/buyer_bridge.csv` | cross-source canonical buyer key table |
| `data/processed/week2_cleaning_report.md` | cleaning rules, impacts, limitations |
| `data/processed/decp_renewal_linking_report.md` | DECP renewal linking method note |
| `data/processed/*_field_profile.{csv,md}` | field-by-field profiling tables |
| `data/processed/source_comparison.{csv,md}` | BOAMP vs DECP comparison |
| `reports/figures/` | duration histograms, EDA plots |
| `reports/week1_summary.md` | **Week-1 summary report** |

## Key technical notes

- BOAMP is queried via the Opendatasoft Explore API
  (`boamp-datadila.opendatasoft.com`, dataset `boamp`); `api.boamp.fr`
  redirects there. The API caps `offset+limit` at 10,000, hence per-year queries.
- CPV codes live inside the JSON-encoded `donnees` field, in **two formats**:
  legacy BOAMP forms (≤2023) and EU **eForms/UBL** (2024+). `scripts/utils.py`
  parses both; server-side CPV filtering uses `LIKE` pre-filters on both
  serializations, re-verified client-side.
- DECP has no queryable API. The source used is the **tabular consolidation**
  `decp.parquet` (dataset "DECP consolidées – format tabulaire" on
  data.gouv.fr, stable URL
  `https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432`,
  ~210 MB, updated daily): full history in one flat SIRENE-enriched table.
  The official JSON "fichiers consolidés" were explored first but are
  schema-inconsistent across vintages (`marches: [...]` vs
  `marches.marche: [...]`) and are not per-year censuses — kept only as a
  documented fallback.
- The current official survival-modeling handoff is BOAMP-only because BOAMP
  and DECP do not share a reliable direct linking key for a robust contract-level
  merge. DECP remains a later enrichment path rather than a prerequisite for
  Phase 2.
- Week 1 deliberately contains **no modeling** (see internship guide §4.1.1).
