# Method-Comparison Report Consistency Audit

**Date:** 2026-07-08  
**Scope:** reports, notebooks, generated CSVs, generated figures, rendered PDFs,
and README/project notes after the no-ground-truth linkage method-comparison
experiment.

## Audit result

**Status:** PASS with limitations documented.

All required method-comparison outputs exist, the three report PDFs rebuild, and
the current selected method is consistent across the updated report/front-matter
sections and project notes. Older 665-event results are retained only as
historical pre-calibration provenance.

## Current selected method

- Method: M0 calibrated balanced composite rule.
- Thresholds: text similarity >= 0.50, composite score >= 0.50, W = 6 months,
  corrected generic CPV scoring, no margin floor.
- Final recommendation: retain M0 balanced as the current main method.
- Best alternative sensitivity candidate: M2 balanced.
- Final selected dataset:
  `data/processed/boamp_phase2_survival_method_m0_balanced.csv`.

## Real BOAMP diagnostics

Real BOAMP precision and recall are not directly observable because BOAMP has no
official renewal-chain ground truth. The values below are diagnostic outputs.

| Method | Variant | Events | Event rate | Negative-control acceptance | Manual audit decided n | Manual audit precision |
|---|---|---:|---:|---:|---:|---:|
| M0 | balanced | 269 | 0.222314 | 0.094243 | 32 | 0.437500 |
| M2 | balanced | 256 | 0.211570 | 0.078076 | 35 | 0.342857 |
| M0 | strict | 79 | 0.065289 | 0.003549 | 14 | 0.857143 |

## Synthetic benchmark metrics

| Method | Variant | Precision | Recall | False positives | False negatives | Synthetic event rate |
|---|---|---:|---:|---:|---:|---:|
| M0 | balanced | 0.575011 | 0.568142 | 949 | 976 | 0.496222 |
| M2 | balanced | 0.678521 | 0.641593 | 687 | 810 | 0.474889 |
| M0 | strict | 0.775180 | 0.381416 | 250 | 1398 | 0.247111 |

## Survival comparison

| Method | Variant | n | Events | Event rate | KM median reached | S12 | S24 | S48 | S60 | Cox C-index | Best AFT | AIC |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---:|
| M0 | balanced | 1210 | 269 | 0.222314 | no | 0.959326 | 0.922993 | 0.832499 | 0.751797 | 0.544208 | LogNormalAFT | 3542.540041 |
| M2 | balanced | 1210 | 256 | 0.211570 | no | 0.958237 | 0.919423 | 0.840588 | 0.756075 | 0.562131 | LogNormalAFT | 3372.175783 |
| M0 | strict | 1210 | 79 | 0.065289 | no | 0.989887 | 0.981047 | 0.954612 | 0.916330 | 0.538096 | LogNormalAFT | 1242.829380 |

Operational 12/24-month risk indicators are available for M0 balanced only:
1,204 rows, median p12 = 0.019800, median p24 = 0.062400.

## Active-learning review sample

`reports/tables/validation/active_learning_review_sample.csv` contains 150
rows: 25 each for near-threshold pairs, high-score generic CPV pairs, event=0
high-nearest-candidate pairs, low top1-top2 margin pairs, high-text CPV mismatch
pairs, and same-buyer/same-CPV weak-text pairs.

## PDF rebuilds

- `reports/phase1_technical_report.pdf` rebuilt successfully.
- `reports/internship_report.pdf` rebuilt successfully.
- `reports/data_quality_report/data_quality_report.pdf` rebuilt successfully.

LaTeX logs contain only float-placement warnings in the technical report after
rerun. No LaTeX errors, missing figures, undefined references, or duplicate PDF
destination warnings remain in the final logs.

## Language and consistency checks

- No report now presents the old 665-event output as the current main result.
- No report claims that the BOAMP event variable is an official renewal-chain
  label.
- No report claims that real BOAMP precision or recall are known.
- The synthetic benchmark is described as controlled validation evidence, not
  proof of real BOAMP truth.
- `event = 0` is described as censored/no observed link under the rule, not as a
  verified absence of recurrence.

## Archive decision

No files were moved to archive in this pass. Older baseline files remain useful
for provenance and are now explicitly labelled as historical or pre-calibration
where they are referenced.

## Addendum: L3 verification and Cox PH gap closure (2026-07-08, same day)

A follow-up pass verified L3 (survival analysis notebook: KM, validated Cox
model, parametric comparison incl. Weibull, 12/24-month predictions,
high-risk table) directly against `boamp_phase2_survival_method_m0_balanced.csv`
and found:

- That file is row-identical (event, durations, covariates) to
  `boamp_phase2_survival_calibrated_balanced.csv`, so all existing KM/Cox/AFT/
  risk-indicator outputs already are the M0 balanced results.
- The Cox C-index appeared as both 0.544 and 0.592 across reports. Root
  cause: two different Cox specs on the same data (richer, category-aware,
  penalizer 0.1 -> 0.592; reduced 3-covariate, penalizer 0.05, used for this
  M0/M1/M2/strict comparison -> 0.544). **0.544 is confirmed as the official
  L3 number**; one stray 0.592 reference in `internship_report.tex` was fixed.
- The official 0.544 spec had never had a Schoenfeld PH-assumption test run
  on the balanced data. Closed: `declared_duration_months` violates PH
  (p<1e-24), `dur_was_imputed` and `start_year` pass — same pattern as the
  pre-calibration model. Output:
  `reports/tables/survival/m0_balanced_cox_ph_assumption_test.csv`.

Full detail in `AUDIT.md`, section "L3 verification and Cox C-index
resolution (2026-07-08)". **L3 status: Done.**
