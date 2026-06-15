# Week 1 — Exploration and Mapping of Data Sources (BOAMP / DECP)

First week of the Gigalis predictive-modeling internship: explore and document
the open public-procurement data sources **before writing any modeling code**.
Scope: digital contracts (CPV 48 software, 72 IT services, 32 telecom,
35 security), Pays de la Loire (departments 44/49/53/72/85), 2015–2024.

## Setup

```bash
pip install -r requirements.txt
```

## Run order

```bash
# Phase 1 — Data acquisition
python scripts/task1b_boamp_full_fetch.py    # full BOAMP download (3,181 notices)
python scripts/task3_decp_fetch_profile.py   # download + filter + profile DECP (~210 MB download)

# Phase 2 — Profiling and comparison (read from Phase 1 outputs)
python scripts/task2_boamp_profile.py        # BOAMP field profiling + deep-dives
python scripts/task4_compare.py              # BOAMP vs DECP comparison table
python scripts/task5_duration_analysis.py    # duration-reliability analysis + figures

# Phase 3 — Cleaning and survival dataset
python scripts/task7_week2_cleaning.py       # shared cleaning functions + DECP cleaning
python scripts/task_boamp_full_clean.py      # apply cleaning to full BOAMP data
python scripts/task6_renewal_linking.py      # DECP renewal links (survival labels)
python scripts/task_boamp_full_survival.py   # BOAMP survival dataset (APPEL_OFFRE only)
python scripts/task8_unified_survival.py     # combined BOAMP + DECP survival dataset
```

Each phase depends on the previous. Tasks 2/4/5 read the CSVs produced by task1b
and task3. The original 500-notice sample (`task1_boamp_fetch.py`) is kept for
reference but superseded by the full download.

## Outputs

| Path | Content |
|---|---|
| `data/raw/boamp_full/` | raw full BOAMP API pages (JSON, verbatim) |
| `data/raw/boamp_sample/` | original 500-notice sample pages (reference only) |
| `data/raw/decp/` | DECP download — decp.parquet (git-ignored, re-downloadable) |
| `data/processed/boamp_full_flat.csv` | **3,181 BOAMP notices, flattened** (primary) |
| `data/processed/boamp_full_clean.csv` | **3,181 notices, cleaned** — buyer keys, amounts, durations, taxonomy |
| `data/processed/boamp_full_survival.csv` | **1,933 APPEL_OFFRE survival records** — event/censoring, ±12 month window |
| `data/processed/boamp_full_survival_report.md` | survival dataset composition report |
| `data/processed/boamp_sample_flat.csv` | 500-notice BOAMP sample (reference only) |
| `data/processed/decp_sample_flat.csv` | filtered DECP contracts (3,039) |
| `data/processed/decp_clean.csv` | DECP with buyer keys, cleaned amounts/durations, taxonomy tags |
| `data/processed/decp_renewal_links.csv` | DECP contracts with linked renewal event/censoring durations |
| `data/processed/unified_survival.csv` | **3,512 combined BOAMP+DECP survival records** |
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
- Week 1 deliberately contains **no modeling** (see internship guide §4.1.1).
