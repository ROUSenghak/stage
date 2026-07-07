# Project Audit — Current State of the Gigalis BOAMP Renewal Repository

**Audit date:** 2026-07-05 (calibrated event-definition update)
**Scope:** What the internship directory *actually contains now* — verified against the live
CSVs, the survival result tables, and the source code — versus the two rendered PDFs
(`stage_dataset.pdf` = `reports/phase1_technical_report.tex`,
`stage_dataset (1).pdf` = `reports/internship_report.tex`).

Every number below was checked directly against a file in this repository; the "Source" column
names that file.

---

## 0. Current calibrated recommendation (2026-07-05, Sentence-Transformer calibration)

The recommended analysis uses the calibrated **balanced** proxy-event rule,
selected after the synthetic benchmark was re-scored with the **same
Sentence-Transformer encoder as the real pipeline**
(`paraphrase-multilingual-MiniLM-L12-v2`): text similarity ≥ 0.50, composite
score ≥ 0.50, W=6, corrected generic CPV scoring, and no margin floor.

| Rule | Thresholds (text / composite) | Real BOAMP events | Linking rate | Main use | Source |
|---|---|---:|---:|---|---|
| Broad | 0.40 / none | 490 / 1,210 | 40.5% | high-recall sensitivity | `reports/tables/validation/recommended_event_rules.csv` |
| Balanced | 0.50 / 0.50 | 269 / 1,210 | 22.2% | recommended survival input | same |
| Strict | 0.70 / 0.65 | 79 / 1,210 | 6.5% | high-precision sensitivity | same |

The balanced survival-ready file is
`data/processed/boamp_phase2_survival_calibrated_balanced.csv`. Readiness
integrity checks passed for all three rules: no missing/non-positive durations,
no duplicate contract IDs, and no event without a renewal ID; the strict rule is
flagged `LOW_EVENTS` (79 < 100) for Cox/AFT stability
(`reports/tables/validation/calibrated_survival_readiness.csv`).

Calibrated survival rerun:

| Rule | Events | KM median | Survival 48m | Cox C-index | Source |
|---|---:|---:|---:|---:|---|
| Broad | 490 | not reached | 0.683 | 0.626 | `reports/tables/survival/calibrated_rule_km_summary.csv`, `calibrated_rule_cox_comparison.csv` |
| Balanced | 269 | not reached | 0.833 | 0.592 | same |
| Strict | 79 | not reached | 0.958 | 0.607 | same |

For the balanced rule, the best parametric AFT model by AIC is LogNormalAFT
(AIC 3,544.8, ahead of Weibull 3,571.8 and LogLogistic 3,580.5;
`reports/tables/survival/calibrated_balanced_aft_comparison.csv`).

Operational 12/24-month risk indicators were re-scored under the balanced rule
(`scripts/task_section16b_calibrated_risk_indicators.py`): 1,204 scored
contracts, mean p12m = 0.023, mean p24m = 0.068, max p12m = 0.073, expected
renewals 27.5 (12m) / 82.3 (24m), top buyer SIREN:234400034 (2.5 expected),
top segment IT Services & Consulting (10.8 expected). Outputs:
`reports/tables/survival/*_calibrated_balanced.csv`.

Interpretation: real BOAMP still has no legal renewal-chain ground truth. The
calibrated labels are proxy recurrences: identifiable reappearances of similar
procurement needs under the selected rule. The older 665-event handoff remains
below as the pre-calibration baseline.

---

## 1. The problematic (unchanged, accurate)
BOAMP notices contain **no explicit renewal field**: a call for tenders never states "this
replaces contract X." The renewal event must be reconstructed from observable signals (buyer
identity, contract text, CPV, timing). The reconstructed `event` is therefore a **proxy**, not a
legally certified renewal. The two structural weaknesses that bound everything downstream:

- **Weak buyer identity** — only ~12.8% of unique buyer keys are SIRET-anchored; the rest are
  normalised-name keys that can fragment one entity (`buyer_bridge.csv`, `boamp_full_clean.csv`).
- **Administrative-ceiling durations** — ~69.5% of declared durations fall on exactly 12/24/36/48
  months (legal maxima, not observed behaviour), so declared duration is a **covariate, not the
  survival target**.

## 2. Method (verified in code — matches the PDFs)
- **Renewal linking (core).** Per eligible source AO, composite score over same-buyer candidates:
  `S = 0.40·text + 0.25·cpv + 0.20·temporal + 0.15·buyer`.
  `cpv` is a hierarchy-based score (1.00 full code → 0.80 category → 0.60 class → 0.40 group → 0.20 division → 0.00; generic codes capped at 0.20). When CPV is missing it is **excluded** and the remaining weights are renormalized: `S = (0.40·text + 0.20·temporal + 0.15·buyer)/0.75` (flag `cpv_used_in_score`).
  Hard filters: `text ≥ 0.20`, gap `∈ [6, 72]` months, window `W = 6`, default duration `48`.
  Text = Sentence-Transformer `paraphrase-multilingual-MiniLM-L12-v2` cosine similarity.
  *Source:* `boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb`,
  `scripts/link_confidence.py`.
- **Strict confidence flag.** `high_confidence_strict = event==1 ∧ S ≥ 0.70 ∧ Δ ≥ 0.05`
  (margin Δ = best − second-best). *Source:* `scripts/link_confidence.py`, commit `be41ed5`.
- **Taxonomy.** Rule-based CPV-prefix → keyword mapping (`scripts/task7_week2_cleaning.py`,
  `data/processed/taxonomy.csv`). **Not** a trained NLP classifier.
- **Survival.** Kaplan–Meier (global + stratified), log-rank, Cox PH (uni/multivariate, ridge
  λ=0.1), parametric AFT (Weibull / log-normal / log-logistic) by AIC, plus an A/B/C event-
  definition sensitivity analysis. *Source:* `notebooks/02_survival_modeling_boamp.ipynb`,
  `_build_survival_notebook.py`, `reports/tables/survival/`.
- **Not implemented:** trained NLP classifier; change-point / trend detection. (Both PDFs state
  this honestly — confirmed accurate.)

## 3. Study scope
CPV divisions 48/72/32/35; Pays de la Loire departments 44/49/53/72/85; period 2015–2024;
official path **BOAMP-only**.

## 4. Results (verified)
| Quantity | Value | Source file |
|---|---|---|
| Source AO → censored upfront → eligible | 1,933 → 723 → 1,210 | `boamp_renewal_linking_quality/outputs/boamp_linking_stats.csv` |
| Linked renewals / linking rate | 665 / **54.96%** (≈55.0%) | `data/processed/boamp_phase2_survival.csv` |
| Lexical baseline (Jaccard, W=6) | 7.6% (146/1,933); 11.3% at the earlier W=12 setting | `data/processed/boamp_full_survival.csv` |
| `high_confidence_strict` | 75 | survival CSV |
| Composite mean (events) | 0.5545 | survival CSV |
| `dur_was_imputed` | 295 (24.4% of eligible) | survival CSV |
| Sensitivity A / B (events·KMmed·CoxC) | 665·50.1·0.6317 / 400·>100·0.6162 | `reports/tables/survival/sensitivity_comparison.csv` |
| Best parametric (AIC / C) | Log-normal 7068.4 / 0.6548 | `reports/tables/survival/parametric_aic_comparison.csv` |
| Cox HRs (significant, multivariate) | declared_duration 0.991 (p<0.001), start_year 1.071 (p<0.001); univariate declared_duration 0.987 | `reports/tables/survival/cox_multivariate_results.csv` |

**Note (2026-06-24 re-run with SIREN enrichment):** The phase-2 linking notebook was re-run
using `buyer_key_enriched` as the active grouping key. The 23 SIREN buyer merges expanded the
candidate pool, adding 8 renewal links (+0.7 pp). Qualitative conclusions were unchanged.

**Note (2026-07-02 W=6 rerun):** Temporal search window changed from W=12 to W=6 months.
Eligibility cutoff moved earlier (est_end ≤ 2024-06-30 vs ≤ 2023-12-31), expanding the eligible
pool to 1,210. Linked events dropped to 665 (55.0%) — narrower window recovers fewer temporal
partners. NO_TEMPORAL_PARTNER failures rose to 491 (from 332 at W=12). KM median rose to 50.1
months. Cox conclusions unchanged: declared_duration (HR 0.991) and start_year (HR 1.071)
remain significant. LogNormal AFT remains best by AIC (7068.4). Composite mean dropped to 0.5545
(lower temporal scores at W=6 reduce the composite). Risk indicators: mean p12m=0.074, expected
renewals=89.7 (vs 208 at W=12 — narrower window shifts model calibration toward lower renewal
probability at 12 months).

**Conclusion on the PDFs:** every headline linking and survival number is correct and reproducible
from the current files.

## 5. Figures present
- `reports/figures/` — BOAMP profile (completion, CPV, durations, top buyers, …), cross-source and
  DECP exploratory plots, and linking diagnostics (`fig_confidence_tiers`, `fig_score_margin`,
  `fig_score_distributions`, `fig_temporal_error`, `fig_threshold_sensitivity`,
  `fig_linking_by_year`).
- `reports/figures/survival/` — `km_global`, `km_by_category`, `km_by_declared_group`,
  `km_by_imputed`, `cox_forest_plot`, `cox_assumptions`, `weibull_survival`,
  `sensitivity_km_comparison`.

---

## 6. Gaps: where the directory has outpaced the two PDFs
These are the only substantive differences between the current repository and the rendered PDFs.
They have been reconciled in the `.tex` sources (see §7).

1. **Handoff schema is 32 columns, not 26.** `boamp_phase2_survival.csv` gained six diagnostics
   columns from commit `be41ed5`: `best_composite_score`, `second_best_composite_score`,
   `score_margin`, `n_candidates_for_source`, `single_candidate_match`, `high_confidence_strict`.
   The PDF Table 13 documented 26.
2. **DECP / unified artefacts exist but the PDFs do not mention them.** Present in
   `data/processed/`: `decp_renewal_links.csv`, `decp_renewal_linking_stats.csv`
   (**8.29% overall — still lexical/Jaccard quality; ST not applied to DECP**),
   `buyer_bridge.csv` (461 mappings), and `unified_survival.csv` (**3,512 rows**, BOAMP+DECP).
   These are **README-documented** (lines 71–83) and **exploratory only** — not a validated handoff.
3. **`boamp_full_survival.csv`** (1,933 rows, 219 events) — full-population Jaccard baseline
   variant — exists and is README-documented but absent from both PDFs.
4. **PDFs not compiled in-repo.** `reports/` contains only `datasets_documentation.pdf`;
   `internship_report.pdf` and `phase1_technical_report.pdf` are not built. The two pasted PDFs are
   external renders.

**Source of truth:** the directory + `README.md` are current; the two `.tex` reports lagged on
items (1) and (2).

## 7. Reconciliation applied to the report sources
- `reports/phase1_technical_report.tex`: "26 columns" → "32 columns"; Table 13 extended with the six
  diagnostics columns; Phase-4 next-step note added listing the exploratory DECP/unified artefacts.
- `reports/internship_report.tex`: "Not implemented" paragraph now states that exploratory DECP links
  and `unified_survival.csv` exist in the repo but are unvalidated and outside the official results.
- Headline numbers updated 2026-06-24 after SIREN enrichment re-run: 697→705 events, 63.4%→64.1%, KM 48.0→48.2 mo, C-index 0.6528→0.6541, LogNormal AIC 7119.9→7176.5.
- Headline numbers updated 2026-07-02 after W=6 rerun: 705→665 events, 64.1%→55.0%, eligible 1,100→1,210, KM 48.2→50.1 mo, C-index 0.6541→0.6317, LogNormal AIC 7176.5→7068.4.

## 8. Out of scope (not done)
Applying the Sentence-Transformer linker to DECP; validating `unified_survival.csv`.

---

# CPV similarity rework — audit (2026-06-22)

Hierarchy-based CPV scoring + missing-CPV renormalization, then full Phase 1 + Phase 2 rerun.

## A. Files changed
- `scripts/task7_week2_cleaning.py` — robust `clean_cpv` (float/`.0`/check-digit safe; restores lost leading zero; keeps 8-digit width). Single source of truth.
- `scripts/task_boamp_full_clean.py` — added derived CPV fields `cpv_full8`, `cpv_group3`, `cpv_category5`, `cpv_is_missing`, `cpv_is_generic` (alongside existing `cpv_clean`, `cpv_div2`, `cpv_class4`).
- `boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb` — new hierarchy `compute_cpv_score` (cell 45); renormalized composite + `cpv_used_in_score` flag (cells 46/53); failure-funnel and info-print cells (49/62) treat missing CPV correctly; markdown cells 44/47/61 updated.
- `scripts/task9_boamp_phase2_handoff.py` — carries `cpv_used_in_score` into `boamp_phase2_survival.csv`.
- Reports: `reports/phase1_technical_report.tex`, `reports/internship_report.tex`, `reports/phase1_data_quality_report.md`, `reports/datasets_documentation.tex`, `AUDIT.md` (formulas, worked example, score tables, tiers, failure funnel, sensitivity, Cox/parametric numbers).

## B. New CPV logic
- Similarity: `1.00` same 8-digit · `0.80` category(5) · `0.60` class(4) · `0.40` group(3) · `0.20` division(2) · `0.00` different division · `NaN` missing. Generic codes (end `000000`) capped at `0.20` (same div) / `0.00` (diff div).
- Composite: with CPV `S = 0.40·text + 0.25·cpv + 0.20·temporal + 0.15·buyer`; **missing CPV** → `S = (0.40·text + 0.20·temporal + 0.15·buyer)/0.75` (flag `cpv_used_in_score=False`). No more arbitrary 0.5.

## C. Commands run
```
python scripts/task_boamp_full_clean.py
jupyter nbconvert --to notebook --execute --inplace boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb
python scripts/task9_boamp_phase2_handoff.py
jupyter nbconvert --to notebook --execute --inplace boamp_renewal_linking_quality/data.ipynb
jupyter nbconvert --to notebook --execute --inplace notebooks/02_survival_modeling_boamp.ipynb
latexmk -pdf reports/phase1_technical_report.tex   # via TinyTeX (installed no-sudo)
latexmk -pdf reports/internship_report.tex
```

## D. Outputs regenerated
`boamp_renewal_candidates.csv`, `boamp_renewal_links.csv`, `boamp_linking_stats.csv`, `boamp_bias_report.csv`, `boamp_link_confidence_diagnostics.csv`, `boamp_full_clean.csv`, `boamp_phase2_survival.csv`; all `reports/figures/fig_*.png` + `reports/figures/survival/*.png`; all `reports/tables/survival/*.csv`; both report PDFs.

## E. Old vs new key metrics
| Metric | OLD | NEW |
|---|---|---|
| Total APPEL_OFFRE | 1,933 | 1,933 |
| Eligible | 1,100 | 1,100 |
| Linked (event=1) | 697 | 697 |
| Linking rate (eligible) | 63.36% | 63.36% |
| Filtered candidate pairs | 5,356 | 5,356 |
| Mean cpv_match_score (event=1) | 0.527 | 0.301¹ |
| Median cpv_match_score | 0.500 | 0.200¹ |
| Mean composite (event=1) | 0.624 | 0.579 |
| HIGH / MEDIUM / LOW tiers | 205 / 348 / 144 | 122 / 372 / 203 |
| Censored rows (event=0) | 403 | 403 |
| KM median survival (Model A) | 48.0 mo | 48.1 mo |
| Cox C-index (multivariate) | 0.6528 | 0.6537 |
| Best parametric (AIC) | LogNormal 7,119.9 | LogNormal 7,119.8 |
| Model B events / C-index | 553 / 0.6202 | 494 / 0.6041 |
| Model C strict events | 132 | 90 |

¹ New `cpv_match_score` is computed over the 646 links with a non-missing CPV (51 missing → NaN, excluded). The drop vs old is expected: the old step function scored same-division as 0.7 and missing as 0.5; the new hierarchy scores same-division as 0.20 and excludes missing.

**Why event counts are unchanged:** CPV is a *scored* component, never a hard filter. The linked set is determined by the text≥0.20 and gap∈[6,72] gates, which did not change. The CPV rework shifts composite *values* (hence confidence tiers, Model B/C, and — via slightly different best-candidate / renewal-partner choices — small KM/Cox/AIC movements), not the linking rate.

## F. Checks passed
- Composite weights sum to 1.0; missing-CPV renorm denominator = 0.75.
- `clean_cpv` unit tests (float, `.0`, leading-zero restore, dash/9th check digit) — all pass.
- `compute_cpv_score` crafted-pair tests (identical / cat5 / class4 / group3 / div2 / diff-div / generic same+diff div / missing→NaN) — all pass.
- event=1: `cpv_used_in_score==False` ⇔ `cpv_match_score` is NaN (0 violations); composite ∈ [0,1].
- `cpv_used_in_score` present in links.csv and phase2_survival.csv; handoff = 1,100 rows / 697 events.
- All four notebooks executed end-to-end without error; both PDFs compiled.
  Page counts as of 2026-06-24: phase1_technical_report.pdf = 69 pp; internship_report.pdf = 7 pp; data_quality_report.pdf = 9 pp.

## G. Warnings / remaining issues
- No system LaTeX; TinyTeX was installed under `~/.TinyTeX` (no sudo) to build the PDFs.
- Business interpretation is unchanged: declared duration and start year remain the only significant Cox predictors; qualitative conclusions stable across Models A/B/C. Model B's KM median is now "not reached" (was 53 mo) because dropping the larger LOW tier (203 vs 144) lifts the curve above 0.5.
- The exploratory Jaccard baseline (`task_boamp_full_survival.py`) and DECP path were **not** rerun — they are not consumed by the official Phase 2 handoff. The reported 11.3% baseline is unaffected.

## H. SIREN buyer enrichment (completed 2026-06-24)

New pipeline: `buyer_siren_enrichment/` (7 steps + `run_all.py`).
Method: for each unique `nomacheteur`, query API Recherche d'Entreprises; score candidates with
`rapidfuzz.fuzz.token_sort_ratio`; classify confidence (HIGH ≥ 85, or ≥ 75 + single or margin ≥ 10;
MEDIUM ≥ 70; LOW ≥ 55; else NO_MATCH). Only HIGH matches get `buyer_key_enriched = "SIREN:" + siren`.

| Metric | Value | Source |
|---|---|---|
| Unique buyers queried | 525 | `boamp_buyer_siren_enriched.csv` |
| HIGH confidence | 275 (52.4%) | same |
| MEDIUM | 21 (4.0%) | same |
| LOW | 32 (6.1%) | same |
| NO_MATCH | 197 (37.5%) | same |
| Keys upgraded to SIREN: prefix | 275 | same |
| SIREN group merges (deduplication) | 23 | `enrichment_quality_summary.csv` |
| APPEL_OFFRE notices with HIGH-conf SIREN | 1,131 / 1,933 (58.5%) | same |
| Jaccard baseline event rate (W=6 rerun) | 146 / 1,933 = 7.6% (was 219 = 11.3% at W=12) | `boamp_full_survival.csv` |
| SIREN-enriched Jaccard event rate (W=6) | 161 / 1,933 = 8.3% (was 234 = 12.1% at W=12) | `boamp_full_survival_enriched.csv` |
| Delta events | +15 (+0.7 pp) | `baseline_vs_siren_enriched_linking_comparison.csv` |
| Log-rank p-value (baseline vs enriched) | 0.38 (not significant) | `baseline_vs_siren_enriched_survival_comparison.csv` |
| Phase-2 cohort (sentence-transformer) | **665 events / 1,210 contracts** (W=6 rerun 2026-07-02; previously 705/1,100 at W=12) | `boamp_phase2_survival.csv` |

Design constraint verified: 0 MEDIUM, 0 LOW rows have `SIREN:` prefix in `buyer_key_enriched`.
`scripts/task_sirene_enrichment.py` is the deprecated predecessor *as a pipeline step*, but it is
**kept in place** because `buyer_siren_enrichment/step2_api_enrich.py` imports its API helper
functions. Its legacy output `boamp_full_clean_sirene.csv` (superseded by
`data/processed/boamp_full_clean_siren_enriched.csv`) was moved to `archive/obsolete_20260702/data/`.
Reports updated: `data_quality_report.tex` has full SIREN section; `internship_report.tex` and
`phase1_technical_report.tex` updated to mark enrichment as completed (both PDFs recompiled 2026-06-24).

---

# Consistency re-audit, cleanup, and manual validation (2026-07-02, second pass)

## I. Consistency fixes applied
The W=6 rerun (earlier on 2026-07-02) had updated headline numbers but left many
secondary numbers stale. Fixed in this pass (all verified against live outputs):
- `reports/phase1_technical_report.tex`: eligibility funnel (833→723, equation now
  states est_end + W ≤ 2024-12-31); abstract Model B line (0.645/52.8/45.2% →
  0.616/not reached/33.1%); start_year HR 1.094→1.071 (abstract, findings,
  multivariate table); full univariate + multivariate Cox tables refreshed from
  `reports/tables/survival/*.csv`; AFT table (LogLogistic 7,154.7/0.660, Weibull
  7,240.3/0.619, LogNormal C 0.655); confidence tiers 148/349/208 → **99/301/265**;
  four-tier caption (42/46/413/164; strict 75 = 42+33); margin stats (501 multi,
  43.7% < 0.05, 30.3% ≥ 0.10); score-stats table (composite mean 0.554 etc., CPV
  n=622); duration stats + temporal-error caption (506/159, σ=2.76); placebo
  (0.554/0.428/0.401; 14.9% vs 0.7%); SMD table (0.166/−0.150/…, N-cand 1.506);
  §16 risk indicators fully refreshed (1,204 scored / 6 excluded; p12 mean 0.075
  max 0.288; expected 89.7/259.9; tiers 0/6/1,198; new top-10 contracts, top-10
  buyers (SIREN-keyed), segment table; buyer ranking 321 rows); reproducibility
  table (1,210/1,210/3,201/67); enrichment appendix (724 SIREN + 2 SIRET / 484
  NAME over 1,210; annotated file regenerated; breakdown HIGH 724 / MED 91 /
  LOW 49 / NO_MATCH 346); category/log-rank narrative (category p=0.025 is now
  marginally significant; IT Services HR 1.230 p=0.037); dur_was_imputed 24.4%;
  buyer table (324 unique buyers); sensitivity figure caption (2 curves only).
- `reports/internship_report.tex`: eligible 1,100→1,210 / censored 833→723;
  33 cols; SIREN split 724(+2)/484; Model C C-index 0.488→0.455; scored contracts
  1,097→1,204; robustness bullets (threshold, placebo, SMD) updated; Cox table
  CI + IT-Services row added.
- `reports/data_quality_report/data_quality_report.tex`: 724/484 split ×3;
  24.4% imputed; uncertain-exclusion 942/397/0.579; SMD paragraph; cohort-year
  paragraph (51–67%, 2023: 8/33).
- **Lexical baseline corrected everywhere:** the Jaccard baseline was re-run at
  W=6 → **146/1,933 = 7.6%** (enriched 161 = 8.3%, log-rank p=0.38). The old
  11.3%/12.1% figures were W=12 values; all reports/READMEs/notebook cells now
  cite 7.6% (W=6) and label 11.3% as the historical W=12 setting.
  `boamp_linking_stats.csv` regenerated with `prev_baseline_pct = 7.6` (linking
  notebook re-executed; links output identical: 1,210/665; phase2 handoff
  md5-identical).
- `data/processed/boamp_phase2_survival_siren_enriched.csv` regenerated
  (was stale at 1,100 rows; now 1,210 via `buyer_siren_enrichment/step7_compare.py`).
- AUDIT.md itself: dur_was_imputed 276→295 (24.4%); HR 0.987 labeled as
  univariate (multivariate is 0.991).
- Known subtlety (documented, not changed): eligibility is decided on the
  publication-date-based estimated end; the exported `estimated_end_date` uses
  the award-refined start, so a few rows show est_end past 2024-06-30.

## II. Cleanup (see `archive/obsolete_20260702/README.md`)
Archived: 7 report snapshots (`*_before_consistency_fix.*`, `*_before_restructure.tex`),
2 stale root-level PDF duplicates, legacy `boamp_full_clean_sirene.csv`, and the
W=12-era validation sample/workbook (with its 17 partial hand labels). Deleted:
root LaTeX build artifacts and `__pycache__`. Kept: `scripts/task_sirene_enrichment.py`
(imported by `buyer_siren_enrichment/step2_api_enrich.py`), the 500-notice sample
files (reference per README), and the historical audit notes under `reports/audit/`.

## III. Manual validation of the proxy event (EXECUTED)
150 stratified cases audited against full official BOAMP records; active
counter-search over the whole corpus for the 50 unlinked sources.
**Results:** linked 100 → TP 14 / FP 82 / uncertain 4; unlinked 50 → TN 41 /
FN 6 / uncertain 3. Precision 0.146 raw, **≈0.088 stratum-weighted** to the 665
events; HIGH tier & strict flag 0.50; text ≥ 0.80 → 1.00 (11/11); MEDIUM 0.09;
LOW 0.00; CPV-exact 0.41. Missed-renewal rate 12.8% (≈70/545 censored); proxy
recall ≈ 0.46 (approximate). FP causes: nearest same-buyer notice is a different
need; generic CPV credited as exact; low text floor; 2 buyer over-merges
(région vs préfecture). FN causes: early renewals before the ±6-month window;
buyer renames; annual cycles missed by weeks.
**Conclusion:** the event variable is NOT validated at the baseline definition;
only the high-text-similarity core is a reliable renewal signal. All three
reports now state this. Files: `event_validation/outputs/manual_validation_audit_labeled.csv`,
`.../boamp_event_validation_audit.xlsx` (Audit_Results sheet),
`.../manual_validation_metrics.csv`, `event_validation/manual_validation_summary.md`.

---

# End-to-end reconciliation pass (2026-07-05, post-calibration)

Full problem-statement → methodology → code → outputs → reports audit. Every
headline number was re-verified against a fresh execution of the current code.

## A. Reproducibility verified (fresh reruns)

- **Calibrated chain (notebooks 04 → 05 → 06 → 07)** re-executed end-to-end
  (Python 3.12 framework kernel): all outputs byte-identical to the committed
  CSVs — synthetic corpus, threshold grid, `recommended_event_rules.csv`
  (broad 490 / balanced 343 / strict 106 over 1,210), calibrated survival
  datasets, KM/Cox/AFT tables (C 0.626/0.591/0.600; LogNormal AIC 4,308.4).
- **Baseline chain (notebook 02 + `task_section16_risk_indicators.py`)**
  re-executed: all tables reproduce numerically (only equal-score tie-order
  swaps in `top20_renewal_risk.csv` / `buyer_renewal_risk_ranking.csv` and
  ~1e-14 float noise in Cox coefficients).
- Environment note: the notebooks execute under the framework Python 3.12
  (has `lifelines`/`nbconvert`, no `sentence_transformers`); the project
  `.venv` has `sentence_transformers` (for the linking notebook) but no
  `lifelines`. Notebook 04's TF-IDF text-similarity fallback claim is true
  for its execution kernel, not for `.venv`.

## B. Inconsistencies found and fixed in this pass

1. `phase1_technical_report.tex` data dictionary + margin section said
   **133 single-candidate / 572 multi-candidate** links — stale W=12 numbers
   (133+572=705). Actual W=6 data: **164 / 501** (`boamp_phase2_survival.csv`).
   Fixed in three places.
2. `phase1_technical_report.tex` sensitivity protocol described Model A as
   "composite ≥ 0.20, text ≥ 0.20" — no composite floor exists in code
   (same error class as the 2026-06-23 audit item A3, in a spot that pass
   missed). Fixed to "text ≥ 0.20, all accepted links; no composite floor".
3. **Temporal hold-out validation was implemented but reported nowhere.**
   Notebook 02 §12 trains on start_year ≤ 2021 (1,088 rows / 604 events) and
   tests on ≥ 2022 (116 rows / 60 events): train C 0.612, test C 0.543.
   Added to `phase1_technical_report.tex` (new subsubsection) and
   `internship_report.tex` (new paragraph). This answers the guide's
   Week-7 temporal-validation requirement.
4. Notebook 02 markdown/print claimed the temporal test set is "73 rows,
   ~50 events" — stale 1,100-row-era numbers; actual 116/60. Fixed in
   `_build_survival_notebook.py` (print now dynamic), notebook rebuilt and
   re-executed; all survival tables unchanged.
5. **Operational risk indicators (§16 / internship §4.3) still use the
   pre-calibration 665-event model** while the recommended definition is the
   calibrated balanced rule. Explicit event-definition notes added to both
   reports; re-scoring under the balanced rule remains a pending step.
6. `scripts/nlp_propagate_labels.py` docstring claimed it writes
   `boamp_phase2_survival.csv`; it actually writes
   `boamp_phase2_survival_nlp.csv` (never overwrites the handoff). Fixed.
7. Internship report pipeline table marked the NLP classifier "Not done ---".
   Updated to **Partial**: scaffolding exists (`scripts/nlp_*.py`,
   `notebooks/03_nlp_classification.ipynb`, 350-row annotation sample drawn),
   but `boamp_annotation_gold.csv` is unfilled and no model is trained.
   Notebook 03 is unexecuted and depends on the missing gold file.

## C. Verified-correct (no change)

- Internship report: all §4 numbers (665/1,210/55.0%; KM 50.1; Cox 0.6317;
  AIC 7,068.4 / 7,154.7 / 7,240.3; log-rank table; category table sums to 665;
  164/501/219(43.7%)/75 link quality; risk table 1,204 / 0.074 / 0.216 /
  0.288 / 6 / 1,198 / 89.7 / 259.9 / SIREN:234400034 9.3 / IT Services 30.4;
  Model C 75 / 6.2% / 0.455 from `uncertain_link_exclusion_summary.csv`).
- Calibration update sections present and numerically correct in all four
  reports (`internship`, `phase1_technical`, `data_quality`,
  `datasets_documentation`) + README + `validation_robustness_report.md` +
  `calibrated_event_definition_summary.md`.
- `boamp_linking_stats.csv` (1,933/723/1,210/665/54.96/7.6/W=6/0.20/48),
  candidates 3,201, links 1,210/665 — all match the reports.
- Notebook 06 re-scoring logic mirrors the linking notebook exactly
  (temporal `1−|gap−dur|/W` clipped, CPV hierarchy 1.0/0.8/0.6/0.4/0.2 with
  generic cap before exact-match, missing-CPV renorm /0.75, same tie-break
  sort, strict flag requires margin — single candidates never auto-promoted).
- Confidence tiers 99/301/265 (events ≥0.70 / 0.50–0.70 / <0.50) and
  four-tier 42/33 recomputed from data — match reports.

## D. Known scope gaps vs the internship guide (disclosed, not fixed)

- **Phase 4 (change-point/trend detection): not implemented** — one of the
  guide's three core sub-problems; all reports disclose this.
- **Phase 2 NLP (deliverable L2): scaffolded only** — annotation gold file
  pending, no trained classifier, no kappa/F1.
- Guide's Week-8 list includes **generalized gamma** AFT — repo fits
  Weibull/log-normal/log-logistic instead (reports do not overclaim).
- Guide asks for **confidence intervals on the 12/24-month probabilities**
  — point estimates only in §16.
- Guide's shared-frailty stretch goal: not attempted (disclosed).

## E. Sentence-Transformer recalibration (2026-07-05, same day, after user decision)

The two items flagged in §B.5 and §D were then executed:

1. **Synthetic benchmark re-scored with the real encoder.**
   `sentence-transformers` was installed into the framework Python 3.12 (the
   notebook kernel) and `_build_synthetic_benchmark_notebook.py` was changed to
   score synthetic text similarity with
   `paraphrase-multilingual-MiniLM-L12-v2` (normalized embeddings, cosine, same
   `normalize_objet` text normalization as the linking notebook). The TF-IDF
   fallback remains only for environments without the package/model, and the
   algorithm-consistency audit records the backend actually used. Notebooks
   04–07 were rebuilt/re-executed. **The selected rules changed**:

   | Rule | TF-IDF-era (superseded) | ST calibration (current) |
   |---|---|---|
   | Broad | text 0.40, 490 events (40.5%) | unchanged |
   | Balanced | text 0.50, no composite floor, 343 events (28.3%) | text 0.50 + composite 0.50, **269 events (22.2%)** |
   | Strict | text 0.55 + composite 0.65, 106 events (8.8%) | text 0.70 + composite 0.65, **79 events (6.5%)**, LOW_EVENTS flag |

   The §A byte-identical reproduction statement therefore now applies to the
   TF-IDF-era outputs as they existed at that time; the current committed
   outputs are the ST-calibration ones summarized in §0. Balanced survival:
   KM median not reached, S48 = 0.833, Cox C = 0.592, LogNormalAFT best
   (AIC 3,544.8). All reports/README updated to these values.

2. **Risk indicators re-scored under the balanced rule** via the new
   `scripts/task_section16b_calibrated_risk_indicators.py` (same design as
   section 16: LogNormal AFT, same covariates, prediction date 2024-12-31,
   deterministic tie-breaking): 1,204 scored, mean p12m 0.023 / p24m 0.068,
   max p12m 0.073, all contracts in the Low tier, expected renewals 27.5 (12m)
   / 82.3 (24m). The pre-calibration section-16 outputs are retained for
   comparison; both reports now cite the calibrated numbers as current.

---

# Full pipeline refresh and reproducibility audit (2026-07-06)

The complete pipeline was re-executed from preprocessing through report
compilation to confirm that every number in the reports comes from actual
current outputs, and that the repository is fully consistent with the
calibrated methodology (baseline → no-ground-truth challenge → synthetic
benchmark → calibration → calibrated proxy events → survival → sensitivity).

## A. What was re-run (in order, all exit 0)

1. `scripts/task_boamp_full_clean.py` (preprocessing) — output **byte-identical**.
2. `boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb`
   (candidate generation + baseline linking, Sentence-Transformer) — all five
   CSV outputs **byte-identical** (1,933 → 723 censored → 1,210 eligible → 665
   linked, 54.96%).
3. `scripts/task9_boamp_phase2_handoff.py` — `boamp_phase2_survival.csv`
   **byte-identical** (1,210 rows / 665 events).
4. `notebooks/02_survival_modeling_boamp.ipynb` +
   `scripts/task_section16_risk_indicators.py` (pre-calibration baseline
   survival + risk indicators) — reproduced; only 1e-14 float noise in Cox
   coefficients and equal-probability tie-order swaps at the bottom of
   `top20_renewal_risk.csv` / row order in `buyer_renewal_risk_ranking.csv`.
5. `notebooks/04 → 05 → 06 → 07` (synthetic benchmark → calibration → apply
   rules → calibrated survival) + `scripts/task_section16b_calibrated_risk_indicators.py`.
6. `validation_robustness/validation_robustness_analysis.ipynb` — all CSV
   outputs **byte-identical**.
7. All four LaTeX reports recompiled with TinyTeX latexmk:
   `internship_report.pdf` (13 pp), `phase1_technical_report.pdf` (87 pp),
   `datasets_documentation.pdf` (9 pp), `data_quality_report.pdf` (10 pp).
   No missing figures; no undefined cross-references.

## B. Reproducibility verdict

**Every decision-bearing output reproduced byte-identically**, including:
all three calibrated survival datasets (`*_calibrated_{broad,balanced,strict}.csv`),
`recommended_event_rules.csv`, `calibrated_real_event_definition_summary.csv`,
`calibrated_survival_readiness.csv`, `calibrated_rule_km_summary.csv`, all
`*_calibrated_balanced.csv` risk tables, and every synthetic QC/audit table.

Immaterial drift observed (documented, not a problem):
- Sentence-Transformer encoding is nondeterministic at ~1e-7 float32 level;
  this flips at most ±1 candidate pair at grid-cell threshold boundaries in
  26 of 4,320 rows of `synthetic_threshold_grid.csv` (and 10–16 of 1,440 rows
  of `parameter_calibration_results.csv`), changing precision/F1 in those
  cells by ≤ 0.0013. **Rule selection is unaffected** (selected-rule tables
  byte-identical).
- lifelines Cox/AFT: float noise ≤ 1e-12 (`calibrated_balanced_aft_comparison.csv`,
  `calibrated_rule_cox_comparison.csv`, `cox_multivariate_results.csv`).
- `*_verification.csv` inventory logs differ only in recorded `size_bytes`.
- One equal-frequency buyer-order swap in `synthetic_design_real_distributions.csv`.

## C. Final numbers (verified against fresh execution outputs)

| Quantity | Value | Source |
|---|---|---|
| Eligible source AO | 1,210 (of 1,933; 723 censored upfront) | `boamp_linking_stats.csv` |
| Pre-calibration baseline | 665 events (55.0%) | `boamp_phase2_survival.csv` |
| Lexical Jaccard baseline | 146/1,933 = 7.6% (W=6) | `boamp_full_survival.csv` |
| **Calibrated balanced (MAIN)** | **269 events (22.2%)**; text ≥ 0.50, composite ≥ 0.50, W=6, corrected generic CPV, no margin floor | `recommended_event_rules.csv` |
| Broad sensitivity | 490 events (40.5%); text ≥ 0.40, no floors | same |
| Strict sensitivity | 79 events (6.5%); text ≥ 0.70, composite ≥ 0.65; LOW_EVENTS flag | same |
| Benchmark balanced P/R/F1 | easy 0.777/0.806/0.791 · medium 0.601/0.586/0.593 · hard 0.318/0.302/0.310 | same |
| Balanced KM | median not reached; S(12)=0.959, S(24)=0.923, S(48)=0.833, S(60)=0.752 | `calibrated_rule_km_summary.csv` |
| Cox C-index (broad/balanced/strict) | 0.626 / 0.592 / 0.607 | `calibrated_rule_cox_comparison.csv` |
| Balanced best AFT | LogNormalAFT AIC 3,544.8 (Weibull 3,571.8, LogLogistic 3,580.5) | `calibrated_balanced_aft_comparison.csv` |
| Calibrated risk indicators | 1,204 scored; mean p12m 0.023 / p24m 0.068; max p12m 0.073; expected 27.5 (12m) / 82.3 (24m); top buyer SIREN:234400034 (2.5); top segment IT Services & Consulting (10.8) | `*_calibrated_balanced.csv` |
| Baseline survival (kept as narrative) | KM median 50.1 mo; Cox C 0.6317; LogNormal AIC 7,068.4; sensitivity B 400 events / C 0.6162 | `sensitivity_comparison.csv`, `parametric_aic_comparison.csv` |

## D. Report consistency (all four reports + README checked)

- All reports follow the progression narrative: data source → initial
  proxy-linking → no-ground-truth challenge → synthetic benchmark → benchmark
  metrics → calibration → calibrated dataset → survival → sensitivity →
  limitations. The 665-event output is everywhere labeled the
  **pre-calibration baseline**; the calibrated **balanced** rule is the main
  specification; broad/strict are sensitivity specifications.
- No overclaiming found: no report states the benchmark "proves" real links
  are true; all state it provides controlled evidence under BOAMP-like noise
  and that `event` is a calibrated proxy recurrence outcome.
- The superseded TF-IDF-era rules (balanced 343 / strict 106) appear only in
  the disclosed historical note in `calibrated_event_definition_summary.md`.
- Fixed this pass: re-executing the validation-robustness notebook clobbered
  the manually added "Current Calibration Update (2026-07-05)" preamble of
  `validation_robustness_report.md`; the section is now baked into
  `validation_robustness/_build_validation_notebook.py` so regeneration
  preserves it (restored, ASCII `>=` instead of `≥`).

## E. Remaining limitations / manual-review items (unchanged, disclosed)

- No legal renewal ground truth exists; even calibrated labels are proxy
  recurrences (manual audit: baseline precision ≈ 0.09–0.15).
- Strict rule underpowered (79 events) for Cox/AFT — flagged LOW_EVENTS.
- Notebook 03 (NLP classifier) scaffolded but unexecuted — awaiting manual
  gold labels in `boamp_annotation_gold.csv`.
- Phase 4 change-point/trend detection not implemented; DECP linking remains
  lexical/exploratory; generalized-gamma AFT and CIs on 12/24-month
  probabilities not done.
- Known nondeterminism to expect on future re-runs: ST encoder float noise
  (±1 pair at grid boundaries), lifelines 1e-12 noise, tie-order swaps in
  equal-score rankings.
