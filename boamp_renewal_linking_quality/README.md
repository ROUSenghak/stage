# BOAMP Renewal Linking — EDA & Preprocessing

## Purpose

This folder contains the current **official BOAMP-only renewal-linking workflow**.
It constructs renewal links between original procurement calls and their subsequent
renewals without relying on DECP. The notebook output is the source for the
official Phase 2 handoff exported to `data/processed/boamp_phase2_survival.csv`.

## Background

BOAMP does not provide an explicit field linking an original call (`APPEL_OFFRE`)
to its later renewal. The link must be reconstructed from matching rules:

| Signal | Field | Coverage |
|--------|-------|----------|
| Buyer identity | `buyer_key` (SIRET or normalized name) | 100% (SIRET: 5.8%) |
| CPV category | `cpv_div2`, `cpv_class4` | ~97% |
| Contract object text | `objet` (Sentence-Transformers cosine) | ~98% |
| Temporal proximity | `dateparution` + `duration_clean` | pub date: 100%; duration: 76.6% |

Two key improvements over the existing `task_boamp_full_survival.py` baseline
(146 events / 1,933 AO = 7.6% at the current W=6 window; 219 = 11.3% at the
earlier W=12 setting):

1. **Group by `buyer_key` only** — CPV compatibility becomes a scored component instead
   of a hard filter, recovering renewals where the buyer reclassified the service.
2. **Sentence-Transformers semantic similarity** (`paraphrase-multilingual-MiniLM-L12-v2`)
   instead of TF-IDF / Jaccard — captures meaning beyond lexical overlap, the main
   source of improvement (+30 pp over TF-IDF alone; TF-IDF was measured on the earlier W=12 pool).

## Results

| Method | Linked | Eligible | Rate |
|---|---|---|---|
| Baseline (Jaccard, buyer+CPV group, W=6) | 146 | 1,933 | 7.6% |
| TF-IDF cosine (intermediate, W=12 pool) | 279 | 1,100 | 25.4% |
| **Sentence-Transformers (final, W=6)** | **665** | **1,210** | **55.0%** |

## Contents

```
boamp_renewal_linking_quality/
├── README.md                                         ← this file
├── boamp_renewal_linking_eda_preprocessing.ipynb     ← main notebook
└── outputs/
    ├── boamp_renewal_candidates.csv    all filtered candidate pairs
   ├── boamp_renewal_links.csv         one row per eligible AO (event 0/1)  ← official linking output
    ├── boamp_linking_stats.csv         summary statistics (one row)
    └── boamp_bias_report.csv           failure-reason × CPV cross-tabulation
```

## How to Run

```bash
cd /path/to/stage-1
# Install the notebook dependencies in the project venv:
.venv/bin/python3 -m pip install scikit-learn sentence-transformers
# Launch the notebook:
.venv/bin/jupyter notebook boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb
```

Run all cells top-to-bottom. The notebook is self-contained: it loads
`data/processed/boamp_full_clean.csv` and writes all outputs to `outputs/`.
The Sentence-Transformers model (~120 MB) is downloaded on first run and
cached in `~/.cache/huggingface/`.

Then export the official processed handoff file:

```bash
python scripts/task9_boamp_phase2_handoff.py
```

## Dependencies

Requires `scikit-learn >= 1.3` and `sentence-transformers` in addition to the
base EDA stack (`pandas`, `numpy`, `matplotlib`, `seaborn`).

## Key Outputs

| File | Rows | Description |
|------|------|-------------|
| `boamp_renewal_candidates.csv` | varies | All pairs passing hard filters, before best-match selection |
| `boamp_renewal_links.csv` | 1,210 | One row per eligible AO; `event=1` (665) if a renewal was found — **official BOAMP linking output** |
| `boamp_linking_stats.csv` | 1 | Linking rate (primary = over eligible denominator) |
| `boamp_bias_report.csv` | 67 | Failure reason × CPV breakdown |

The standardized Phase 2 handoff exported by `task9_boamp_phase2_handoff.py`
is written to `data/processed/boamp_phase2_survival.csv`.

The academic PDF figures used by `reports/phase1_technical_report.tex` are
generated directly inside `boamp_renewal_linking_quality/data.ipynb`.

## Linking Rate Definition

- **Eligible AO**: APPEL_OFFRE notices whose expected renewal window (`estimated_end_date ± 6 months`) falls within the study period (2015-01-01 to 2024-12-31).
- **Linked**: eligible AO for which a best-match candidate renewal was found above all thresholds.
- **Linking rate (primary)** = linked / eligible. Right-censored AO (expected renewal after 2024) are excluded from the denominator — they cannot be linked regardless of algorithm quality.

## Assumptions

1. Default duration = 48 months when `duration_clean` is missing.
2. Temporal window = ±6 months around estimated contract end date.
3. `annonce_lie` on ATTRIBUTION notices is a same-contract back-reference, not a renewal signal. Used to extract a more precise contract start date and for calibration.
4. Declared duration is the administrative maximum (base + renewals); actual first renewal may occur earlier.

## Limitations

- 94.2% of buyer keys are name-based; variant spellings of the same buyer may split records into separate groups, creating structural misses.
- Buyers who issued only one notice within the eligible window are structurally uncoverable — the main residual ceiling on the 45.0% unlinked AO.
- CPV removed from hard filters increases recall but may introduce false positives where two unrelated contracts from the same buyer share similar text and fall in the right time window.
