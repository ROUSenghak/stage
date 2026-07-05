# Statistical Explanation Improvements Audit

Date: 2026-06-25
Target PDF: `reports/phase1_technical_report.pdf`
Target source: `reports/phase1_technical_report.tex`

## Current calibration note (2026-07-05)

This file records the 2026-06-25 statistical-explanation cleanup. The current
recommended event definition is now the calibrated balanced rule: text ≥ 0.50,
composite ≥ 0.50, W=6, corrected generic CPV scoring, no margin floor
(Sentence-Transformer calibration). It gives 269 proxy recurrence events among
1,210 eligible BOAMP contracts (22.2%). The older 665/705-event numbers below are historical audit evidence,
not the current recommended modeling input.

## Sections edited

- Abstract Phase 2 summary
- Duration reliability section where the observed renewal gap is defined
- Linking candidate / temporal-score notation blocks
- Dataset construction table for survival and confidence variables
- Score-disambiguation / strict high-confidence section
- New Statistical Roadmap inserted before Survival Analysis: Methods
- Section 12: Survival Analysis: Methods
- Section 13: Survival Results
- Section 14: Sensitivity and Robustness
- Section 15: Operational Risk Indicators
- Section 17: Remaining Work
- Buyer SIREN enrichment summary paragraph in the closing section

## New explanation blocks added

- Statistical Roadmap subsection with compact tool/type/question/result/limitation table
- Purpose / How to read / Limitation blocks for:
  - Kaplan-Meier estimator
  - log-rank test
  - Cox proportional hazards model
  - C-index
  - AFT models
  - proportional hazards assumption
- Log-rank hypothesis block before the summary table:
  - `H_0: S_1(t)=...=S_K(t)` for all `t`
  - `H_1`: at least one survival curve differs
- Post-log-rank interpretation paragraph clarifying which comparisons are significant and which are not
- Concrete Cox interpretation box for:
  - `declared_duration_months` HR = 0.991
  - `start_year` HR = 1.094
- PH assumption explanation clarifying constant hazard ratios vs. constant hazards, Schoenfeld null/alternative, and why AFT is a complementary model
- AFT/AIC explanation clarifying that AIC is a same-dataset comparison criterion, not a p-value or accuracy score
- Robustness framing paragraph explaining Models A/B/C as a stress test of the proxy event definition
- Score-margin diagnostic interpretation block
- Placebo / negative-control interpretation block
- SMD balance definition and interpretation block
- Conditional operational probability explanation plus buyer-level expected renewals formula
- Final statistical conclusion paragraph stating that validation remains internal and precision/recall are still unknown

## Notation changes made

- Time gap notation changed from `\Delta(i,j)` to `g(i,j) = t_j - t_i`
- Linked observed renewal gap changed from `\Delta(i,j^*)` to `g(i,j^*)`
- Score margin notation changed from `\Delta = S(i,j^{(1)}) - S(i,j^{(2)})` to `m_i = S(i,j^{(1)}) - S(i,j^{(2)})`
- Updated affected formulas, captions, worked example, temporal-score definition, strict high-confidence rule, and survival-section references accordingly
- Left `\delta_i` unchanged because it is the survival event indicator and is not part of the notation conflict

## Numerical inconsistencies fixed

- Corrected post-SIREN log-normal AFT AIC from stale `7,119.8` to `7,176.6` using `reports/tables/survival/parametric_aic_comparison.csv`
- Corrected log-logistic and Weibull AIC values in the AFT table to `7,248.8` and `7,380.3`
- Updated the abstract hazard ratios to match the full multivariate Cox table:
  - `declared_duration_months`: `0.991`
  - `start_year`: `1.094`
- Corrected censored-share wording from `36.6%` to `35.9%` in the active report where it referred to the current 395 / 1100 survival cohort
- Corrected `NO_TEMPORAL_PARTNER` prose from `84.1%` to `83.8%`
- Updated manual-validation wording from `50--100 linked pairs` to the documented stratified 150-row sample
- Updated current buyer-fragmentation wording to the enriched survival-population counts:
  - `660` SIREN-keyed rows
  - `440` NAME-keyed rows
- Clarified that the full Cox C-index (`0.6541`) and reduced sensitivity-model C-index (`0.6536`) refer to different model specifications
- Clarified that Model C in the main sensitivity table is the strict 100-event scenario, while the 116-event strict-H.C. row in the threshold sweep is a broader variant including qualifying single-candidate links

## Render and audit findings

- Rebuilt `reports/phase1_technical_report.pdf` successfully with TinyTeX `latexmk`
- No fatal LaTeX errors or undefined references were found in the final build
- Rendered-PDF text audit completed using `pypdf`
- Stale values searched in the rendered PDF:
  - `7,119.8`, `7119.8`, `36.6%`, `0.6524`: not present in active rendered content
  - `697`, `63.4%`, `553`: present only in explicitly labeled pre-enrichment historical comparisons, which are intentional
  - `403`: present only as the decimal `0.403` in the synthetic no-buyer placebo row, not as an old censored-count statement
- Active rendered PDF contains the expected current values including `705`, `395`, `64.1%`, `48.2`, `52.8`, `9.1%`, `0.6541`, and `0.6536`

## Remaining unresolved issues

- The final LaTeX log contains one warning: `Overfull \vbox (684.7559pt too high) has occurred while \output is active []`.
  This appears to be a page-layout/output warning rather than a formula or reference failure, but it was not fully localized further in this pass.
- The rendered PDF still contains historical pre-enrichment values (`697`, `63.4%`, `553`) in explicitly comparative passages. These were retained intentionally because they are labeled as historical baselines.
- No contradictory output CSV was found for the main requested current results. The only important apparent discrepancy is intentional and now explained in the report:
  - `0.6541` = full multivariate Cox model
  - `0.6536` = reduced Cox model used for robustness comparability
