# Calibrated BOAMP Event Definition Summary

**Updated:** 2026-07-08 (method-comparison refresh)  
**Main notebook path:** notebooks 04 to 07, plus
`notebooks/06_linkage_method_comparison_no_ground_truth.ipynb`  
**Important interpretation:** BOAMP has no official renewal-chain ground truth.
Real `event = 1` means a proxy recurrence: an identifiable reappearance of a
similar procurement need under the selected rule.

## What Was Added

- Synthetic benchmark with known synthetic true links, scored with the **same
  Sentence-Transformer encoder as the real pipeline**
  (`paraphrase-multilingual-MiniLM-L12-v2`, normalized embeddings, cosine):
  `notebooks/04_synthetic_boamp_benchmark.ipynb`
- Parameter calibration with synthetic benchmark and real diagnostics:
  `notebooks/05_parameter_calibration_benchmark_and_real.ipynb`
- Real BOAMP calibrated datasets:
  `notebooks/06_apply_calibrated_rules_to_real_boamp.ipynb`
- Calibrated survival rerun:
  `notebooks/07_calibrated_survival_analysis.ipynb`
- Calibrated 12/24-month risk indicators:
  `scripts/task_section16b_calibrated_risk_indicators.py`
- Method comparison without real BOAMP ground truth:
  `notebooks/06_linkage_method_comparison_no_ground_truth.ipynb`

An earlier same-day calibration used a TF-IDF text-similarity fallback (the
notebook kernel then lacked `sentence_transformers`); it selected balanced =
343 events and strict = 106 events. After installing the encoder into the
kernel, the benchmark was re-scored with the real Sentence-Transformer and the
rules below supersede those numbers.

The 2026-07-08 method-comparison experiment treats the calibrated balanced rule
as M0. It compares M0 with M1 probabilistic linkage and M2
active-learning-assisted linkage, with the synthetic pairs scored by the same
Sentence-Transformer encoder as the real pipeline and a selection score that
deliberately excludes the mapped manual-audit term (the audit sample was
stratified on the pre-calibration baseline's own links, so it is
baseline-anchored). The final recommendation **promotes M2 balanced to the
main method** (all five promotion criteria pass), with **M0 balanced retained
as the conservative transparent baseline** sensitivity.

## Recommended Rules

| Rule | Text threshold | Composite threshold | Margin threshold | W | Generic CPV rule | Real events | Linking rate | Use |
|---|---:|---|---|---:|---|---:|---:|---|
| Broad | 0.40 | none | none | 6 | corrected | 490 | 40.5% | high-recall sensitivity |
| Balanced | 0.50 | 0.50 | none | 6 | corrected | 269 | 22.2% | conservative baseline (main until 2026-07-08) |
| Strict | 0.70 | 0.65 | none | 6 | corrected | 79 | 6.5% | high-precision sensitivity |

The selected main method since 2026-07-08 is **M2 balanced** (match-probability
threshold 0.65; 254 events, 21.0%), see the method-comparison result below.

The balanced rule is recommended because it satisfies the synthetic reliability
constraints (medium precision ≥ 0.60, runner-up negative-control pass rate ≤
0.20) while keeping enough real BOAMP events for survival modeling.

## Method-Comparison Result (2026-07-08)

| Method | Variant | Real events | Event rate | Synthetic precision | Synthetic recall | Negative-control acceptance | Mapped-audit diagnostic |
|---|---|---:|---:|---:|---:|---:|---:|
| M0 calibrated composite | balanced | 269 | 22.2% | 0.575 | 0.568 | 0.094 | 0.438 (n=32) |
| M1 probabilistic linkage | balanced | 256 | 21.2% | 0.612 | 0.733 | 0.085 | 0.371 (n=35) |
| **M2 active-learning-assisted (selected)** | balanced | **254** | **21.0%** | **0.612** | **0.733** | **0.079** | 0.371 (n=35) |
| M0 calibrated composite | strict | 79 | 6.5% | 0.775 | 0.381 | 0.004 | 0.857 (n=14) |

M1/M2 balanced improve benchmark-estimated precision and recall over M0
balanced in every scenario and lower the negative-control acceptance rate.
**M2 balanced is the selected main method**: it passes all five promotion
criteria (selection score 0.797 vs 0.741; negative controls not worse; 254
events; smaller synthetic-to-real accepted-link profile shift, 0.045 vs
0.128; same text backend as the real pipeline). The mapped-audit column is a
baseline-anchored diagnostic only (the audit sample came from the
pre-calibration baseline's links; n=32-35 decided pairs per balanced variant)
and was excluded from the selection score. M0 balanced remains the
conservative transparent baseline. Real BOAMP precision and recall are not
directly observable.

## Synthetic Benchmark Reliability

For the M0 balanced rule and the selected M2 balanced method
(Sentence-Transformer scoring):

| Scenario | M0 Precision | M0 Recall | M0 F1 | M2 Precision | M2 Recall | M2 F1 |
|---|---:|---:|---:|---:|---:|---:|
| Easy | 0.777 | 0.806 | 0.791 | 0.812 | 0.924 | 0.865 |
| Medium | 0.601 | 0.586 | 0.593 | 0.619 | 0.764 | 0.684 |
| Hard | 0.318 | 0.302 | 0.310 | 0.409 | 0.501 | 0.450 |

The hard scenario was intentionally difficult: generic CPV, buyer-name noise,
CPV reclassification, missing data, and many false same-buyer candidates. Low
hard-scenario performance means the real BOAMP results should be treated as
proxy labels, not as certified renewal labels.

## Real BOAMP Survival Readiness

All calibrated datasets have 1,210 rows. Integrity checks passed for broad,
balanced, and strict:

- no missing survival duration;
- no non-positive survival duration;
- no duplicate contract ID;
- no event without a renewal candidate ID.

The strict rule is flagged `LOW_EVENTS` (79 events < 100), so its Cox/AFT
estimates should be read as unstable-sensitivity output only.

## Current Survival Results

| Rule / method | Events | KM median | Survival 12m | Survival 24m | Survival 48m | Cox C-index (richer spec) |
|---|---:|---:|---:|---:|---:|---:|
| M0 broad | 490 | not reached | 0.914 | 0.843 | 0.683 | 0.626 |
| M0 balanced (baseline) | 269 | not reached | 0.959 | 0.923 | 0.833 | 0.592 |
| **M2 balanced (selected)** | **254** | not reached | 0.956 | 0.921 | 0.840 | 0.606 |
| M0 strict | 79 | not reached | 0.990 | 0.982 | 0.958 | 0.607 |

(The official reduced-spec C-indices used in the method comparison are 0.553
for M2 balanced and 0.544 for M0 balanced.) For the selected M2 balanced
method, LogNormalAFT is the best AFT model by AIC (3,357.9 in the
method-comparison rerun; Weibull 3,404.4); under M0 balanced the ordering is
the same (LogNormal 3,542.5, Weibull 3,570.2). AIC values are not comparable
across event definitions. The KM median is not reached under any definition,
meaning fewer than 50% of contracts experience the proxy event before
censoring.

## Current Risk Indicators

`scripts/task_section16b_calibrated_risk_indicators.py` refits the LogNormal
AFT (same design as the pre-calibration section 16). Under the **selected M2
balanced method**: 1,204 scored contracts, mean p12m = 0.024, mean p24m =
0.070, max p12m = 0.079 (all contracts in the Low tier), expected renewals
29.0 within 12 months and 84.1 within 24 months; top buyer SIREN:234400034
(2.8 expected 12m), top segment IT Services & Consulting (11.9 expected 12m).
Under the M0 balanced baseline: mean p12m = 0.023, mean p24m = 0.068,
expected renewals 27.5 / 82.3, same leaders.

## Main Files

- Selected survival input (M2 balanced):
  `data/processed/boamp_phase2_survival_method_m2_balanced.csv`
- Conservative baseline input (M0 balanced):
  `data/processed/boamp_phase2_survival_method_m0_balanced.csv`
- Equivalent calibrated balanced input:
  `data/processed/boamp_phase2_survival_calibrated_balanced.csv`
- Method comparison table:
  `reports/tables/validation/linkage_method_comparison.csv`
- Final method recommendation:
  `reports/tables/validation/final_method_recommendation.csv`
- Method survival comparison:
  `reports/tables/validation/method_survival_comparison.csv`
- Rule table:
  `reports/tables/validation/recommended_event_rules.csv`
- Real rule comparison:
  `reports/tables/validation/calibrated_real_event_definition_summary.csv`
- Survival readiness:
  `reports/tables/validation/calibrated_survival_readiness.csv`
- KM summary:
  `reports/tables/survival/calibrated_rule_km_summary.csv`
- Cox comparison:
  `reports/tables/survival/calibrated_rule_cox_comparison.csv`
- Current risk indicators (M2 balanced):
  `reports/tables/survival/renewal_risk_12_24_months_m2_balanced.csv`
- Baseline risk indicators (M0 balanced):
  `reports/tables/survival/renewal_risk_12_24_months_calibrated_balanced.csv`

## Conclusion

Use **M2 balanced** as the main survival-analysis event definition (the
benchmark-preferred method promoted on 2026-07-08). Report **M0 balanced** as
the conservative transparent baseline, and broad/strict as sensitivity checks.
Treat the mapped manual audit as a baseline-anchored plausibility diagnostic,
not as ground truth or a method arbiter. Do not report real precision or
recall for BOAMP as if they were known; real BOAMP only has diagnostic linking
rates, negative-control behavior, limited mapped audit labels, and proxy
recurrence labels.
