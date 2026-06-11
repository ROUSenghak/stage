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
python scripts/task1_boamp_fetch.py          # fetch 500-notice BOAMP sample (API)
python scripts/task2_boamp_profile.py        # BOAMP field profiling + deep-dives
python scripts/task3_decp_fetch_profile.py   # download + filter + profile DECP (~210 MB download)
python scripts/task4_compare.py              # BOAMP vs DECP comparison table
python scripts/task5_duration_analysis.py    # duration-reliability analysis + figures
python scripts/task7_week2_cleaning.py       # Week-2 cleaning, buyer normalization, taxonomy tagging
python scripts/task6_renewal_linking.py      # Week-3 prototype: renewal links + survival-ready durations
```

Each script is independent of the next but Tasks 2/4/5 read the CSVs produced
by Tasks 1 and 3.

## Outputs

| Path | Content |
|---|---|
| `data/raw/boamp_sample/` | raw BOAMP API pages (JSON, verbatim) |
| `data/raw/decp/` | DECP download — decp.parquet (git-ignored, re-downloadable) |
| `data/processed/boamp_sample_flat.csv` | flattened 500-notice BOAMP sample |
| `data/processed/decp_sample_flat.csv` | filtered DECP contracts (3,039) |
| `data/processed/taxonomy.csv` | 10-category tech taxonomy (CPV + keywords) |
| `data/processed/boamp_clean.csv` | BOAMP with buyer keys, cleaned amounts/durations, taxonomy tags |
| `data/processed/decp_clean.csv` | DECP with buyer keys, cleaned amounts/durations, taxonomy tags |
| `data/processed/buyer_bridge.csv` | cross-source canonical buyer key table |
| `data/processed/week2_cleaning_report.md` | Week-2 cleaning rules, impacts, limitations |
| `data/processed/decp_renewal_links.csv` | DECP contracts with linked renewal event/censoring durations |
| `data/processed/decp_renewal_linking_stats.csv` | linking-rate statistics (overall + CPV division) |
| `data/processed/decp_renewal_linking_report.md` | short method/report note for Week 3 |
| `data/processed/*_field_profile.{csv,md}` | field-by-field profiling tables |
| `data/processed/source_comparison.{csv,md}` | BOAMP vs DECP comparison |
| `reports/figures/` | declared-duration histogram + box plot |
| `reports/week1_summary.md` | **one-page Week-1 summary report** |

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
