# BOAMP Renewal Linking — EDA & Preprocessing

## Purpose

This folder contains a self-contained EDA and preprocessing workflow for the BOAMP
dataset, focused on constructing renewal links between original procurement calls and
their subsequent renewals. It is **independent of DECP** and does not share output
files with the main `scripts/` pipeline.

## Background

BOAMP does not provide an explicit field linking an original call (`APPEL_OFFRE`)
to its later renewal. The link must be reconstructed from matching rules:

| Signal | Field | Coverage |
|--------|-------|----------|
| Buyer identity | `buyer_key` (SIRET or normalized name) | 100% (SIRET: 9.1%) |
| CPV category | `cpv_div2`, `cpv_class4` | ~97% |
| Contract object text | `objet` (TF-IDF cosine) | ~98% |
| Temporal proximity | `dateparution` + `duration_clean` | pub date: 100%; duration: 48% |

The main technical improvement over the existing `task_boamp_full_survival.py` baseline
(219 events / 1 933 AO = 11.3%) is to **group by buyer only**, not by `buyer_key + cpv_div2`.
CPV compatibility becomes a scored component instead of a hard filter, allowing the
linking rate to increase substantially.

## Contents

```
boamp_renewal_linking_quality/
├── README.md                                         ← this file
├── boamp_renewal_linking_eda_preprocessing.ipynb     ← main notebook
└── outputs/
    ├── boamp_renewal_candidates.csv    all filtered candidate pairs
    ├── boamp_renewal_links.csv         one row per eligible AO (event 0/1)
    ├── boamp_linking_stats.csv         summary statistics (one row)
    └── boamp_bias_report.csv           failure-reason × CPV cross-tabulation
```

## How to Run

```bash
cd /path/to/stage-1
# Make sure scikit-learn is installed in the venv:
.venv/bin/python3 -m pip install scikit-learn
# Launch the notebook:
.venv/bin/jupyter notebook boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb
```

Run all cells top-to-bottom. The notebook is self-contained: it loads
`data/processed/boamp_full_clean.csv` and writes all outputs to `outputs/`.

## Dependencies

Requires `scikit-learn >= 1.3` in addition to the base `requirements.txt`.
Add `scikit-learn>=1.3` to `requirements.txt` for reproducibility.

## Key Outputs

| File | Rows | Description |
|------|------|-------------|
| `boamp_renewal_candidates.csv` | variable | All pairs passing hard filters, before best-match selection |
| `boamp_renewal_links.csv` | ~1 200 | One row per eligible AO; `event=1` if a renewal was found |
| `boamp_linking_stats.csv` | 1 | Linking rate (primary = over eligible denominator) |
| `boamp_bias_report.csv` | variable | Failure reason × CPV breakdown |

## Linking Rate Definition

- **Eligible AO**: APPEL_OFFRE notices whose expected renewal window (`estimated_end_date ± 6 months`) falls within the study period (2015-01-01 to 2024-12-31).
- **Linked**: eligible AO for which a best-match candidate renewal was found above all thresholds.
- **Linking rate (primary)** = linked / eligible. This is the correct denominator because right-censored AO (expected renewal after 2024) cannot possibly be linked regardless of algorithm quality.

## Assumptions

1. Default duration = 48 months when `duration_clean` is missing.
2. Temporal window = ±6 months around estimated contract end date.
3. `annonce_lie` on ATTRIBUTION notices is a same-contract back-reference, not a renewal signal. It is used to extract a more precise contract start date.
4. Declared duration is the administrative maximum (base + renewals); actual first renewal may occur earlier.

## Limitations

- 90%+ of buyer keys are name-based; variant spellings of the same buyer may split records into separate groups, creating structural misses.
- Contracts from buyers who issued only one notice within the eligible window are structurally uncoverable (~60% of eligible unlinked AO fall into this category).
- TF-IDF captures lexical similarity, not semantic similarity. A contract re-tendered with different wording may be missed even at threshold 0.20.
