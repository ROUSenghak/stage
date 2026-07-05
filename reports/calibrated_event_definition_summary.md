# Calibrated BOAMP Event Definition Summary

**Updated:** 2026-07-05 (Sentence-Transformer calibration)  
**Main notebook path:** notebooks 04 to 07  
**Important interpretation:** BOAMP has no legal renewal-chain ground truth. Real
`event = 1` means a proxy recurrence: an identifiable reappearance of a similar
procurement need under the selected rule.

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

An earlier same-day calibration used a TF-IDF text-similarity fallback (the
notebook kernel then lacked `sentence_transformers`); it selected balanced =
343 events and strict = 106 events. After installing the encoder into the
kernel, the benchmark was re-scored with the real Sentence-Transformer and the
rules below supersede those numbers.

## Recommended Rules

| Rule | Text threshold | Composite threshold | Margin threshold | W | Generic CPV rule | Real events | Linking rate | Use |
|---|---:|---|---|---:|---|---:|---:|---|
| Broad | 0.40 | none | none | 6 | corrected | 490 | 40.5% | high-recall sensitivity |
| Balanced | 0.50 | 0.50 | none | 6 | corrected | 269 | 22.2% | main survival input |
| Strict | 0.70 | 0.65 | none | 6 | corrected | 79 | 6.5% | high-precision sensitivity |

The balanced rule is recommended because it satisfies the synthetic reliability
constraints (medium precision ≥ 0.60, runner-up negative-control pass rate ≤
0.20) while keeping enough real BOAMP events for survival modeling.

## Synthetic Benchmark Reliability

For the balanced rule (Sentence-Transformer scoring):

| Scenario | Precision | Recall | F1 |
|---|---:|---:|---:|
| Easy | 0.777 | 0.806 | 0.791 |
| Medium | 0.601 | 0.586 | 0.593 |
| Hard | 0.318 | 0.302 | 0.310 |

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

## Calibrated Survival Results

| Rule | Events | KM median | Survival 12m | Survival 24m | Survival 48m | Cox C-index |
|---|---:|---:|---:|---:|---:|---:|
| Broad | 490 | not reached | 0.914 | 0.843 | 0.683 | 0.626 |
| Balanced | 269 | not reached | 0.959 | 0.923 | 0.833 | 0.592 |
| Strict | 79 | not reached | 0.990 | 0.982 | 0.958 | 0.607 |

For the balanced rule, LogNormalAFT is the best AFT model by AIC
(AIC = 3,544.8, ahead of Weibull 3,571.8 and LogLogistic 3,580.5).

## Calibrated Risk Indicators (balanced rule)

`scripts/task_section16b_calibrated_risk_indicators.py` refits the LogNormal
AFT on the balanced dataset (same design as the pre-calibration section 16):
1,204 scored contracts, mean p12m = 0.023, mean p24m = 0.068, max p12m =
0.073 (all contracts in the Low tier), expected renewals 27.5 within 12 months
and 82.3 within 24 months; top buyer SIREN:234400034 (2.5 expected 12m), top
segment IT Services & Consulting (10.8 expected 12m).

## Main Files

- Recommended survival input:
  `data/processed/boamp_phase2_survival_calibrated_balanced.csv`
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
- Calibrated risk indicators:
  `reports/tables/survival/renewal_risk_12_24_months_calibrated_balanced.csv`

## Conclusion

Use the **balanced** calibrated rule as the main survival-analysis event
definition. Report broad and strict as sensitivity checks (strict is
underpowered at 79 events). Do not report real precision or recall for BOAMP
unless manual labels are used; real BOAMP only has diagnostic linking rates and
proxy recurrence labels.
