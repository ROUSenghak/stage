# Project Audit — Current State of the Gigalis BOAMP Renewal Repository

**Audit date:** 2026-06-22
**Scope:** What the internship directory *actually contains now* — verified against the live
CSVs, the survival result tables, and the source code — versus the two rendered PDFs
(`stage_dataset.pdf` = `reports/phase1_technical_report.tex`,
`stage_dataset (1).pdf` = `reports/internship_report.tex`).

Every number below was checked directly against a file in this repository; the "Source" column
names that file.

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
  Hard filters: `text ≥ 0.20`, gap `∈ [6, 72]` months, window `W = 12`, default duration `48`.
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
| Source AO → censored upfront → eligible | 1,933 → 833 → 1,100 | `boamp_renewal_linking_quality/outputs/boamp_linking_stats.csv` |
| Linked renewals / linking rate | 705 / **64.09%** (≈64.1%) | `data/processed/boamp_phase2_survival.csv` |
| Lexical baseline | 11.3% | `boamp_linking_stats.csv` |
| `high_confidence_strict` | 100 | survival CSV |
| single-candidate / multi-candidate / margin<0.05 | 133 / 572 / 265 | survival CSV |
| `dur_was_imputed` | 276 (25.1%) | survival CSV |
| Composite mean (events) | 0.5872 | survival CSV |
| Sensitivity A / B (events·KMmed·CoxC) | 705·48.2·0.6541 / 497·inf·0.6061 | `reports/tables/survival/sensitivity_comparison.csv` |
| Best parametric (AIC / C) | Log-normal 7176.5 / 0.6719 | `reports/tables/survival/parametric_aic_comparison.csv` |
| Cox HRs (significant) | declared_duration 0.990 (p≈3e-5), start_year 1.097 (p≈8e-6) | `reports/tables/survival/cox_multivariate_results.csv` |

**Note (2026-06-24 re-run with SIREN enrichment):** The phase-2 linking notebook was re-run
using `buyer_key_enriched` as the active grouping key. The 23 SIREN buyer merges expanded the
candidate pool, adding 8 renewal links (+0.7 pp). The composite score mean for events dropped
from 0.624 to 0.587 because new inter-alias links tend to have lower margins (previously
no candidates existed). Qualitative conclusions are unchanged: declared_duration and start_year
remain the only significant Cox predictors (HR 0.990 and 1.097); LogNormal AFT best by AIC;
risk tiers 0 High / 222 Medium / 875 Low.

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
| Jaccard baseline event rate | 219 / 1,933 = 11.3% | `boamp_full_survival.csv` |
| SIREN-enriched Jaccard event rate | 234 / 1,933 = 12.1% | `boamp_full_survival_enriched.csv` |
| Delta events | +15 (+0.8 pp) | `baseline_vs_siren_enriched_linking_comparison.csv` |
| Log-rank p-value (baseline vs enriched) | 0.47 (not significant) | `baseline_vs_siren_enriched_survival_comparison.csv` |
| Phase-2 cohort (sentence-transformer) | **705 events / 1,100 contracts** (updated: 23 SIREN merges expanded candidate pool, +8 events vs pre-enrichment 697) | `boamp_phase2_survival.csv` |

Design constraint verified: 0 MEDIUM, 0 LOW rows have `SIREN:` prefix in `buyer_key_enriched`.
`scripts/task_sirene_enrichment.py` is the deprecated predecessor; its output `boamp_full_clean_sirene.csv`
is a legacy file superseded by `data/processed/boamp_full_clean_siren_enriched.csv`.
Reports updated: `data_quality_report.tex` has full SIREN section; `internship_report.tex` and
`phase1_technical_report.tex` updated to mark enrichment as completed (both PDFs recompiled 2026-06-24).
