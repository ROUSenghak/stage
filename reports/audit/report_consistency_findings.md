# Report Consistency Audit & Findings

**Date:** 2026-06-25
**Scope:** `internship_report.tex`, `data_quality_report.tex`, `phase1_technical_report.tex`
**Method:** All numbers verified directly against output CSVs (source of truth), not against
PDF/LaTeX text. See `current_results_audit.csv` for the metric-by-metric audit table.

---

## 1. Official current-stage numbers (post-SIREN, 2026-06-24)

| Metric | Value | Source |
|---|---|---|
| Raw BOAMP notices | 3,181 | `boamp_full_clean.csv` |
| APPEL_OFFRE source contracts | 1,933 | `boamp_full_clean.csv` |
| Eligible survival population | 1,100 | `boamp_linking_stats.csv` |
| Linked proxy-renewal events | 705 | `boamp_phase2_survival.csv` |
| Right-censored | 395 | `boamp_phase2_survival.csv` |
| Linking rate (eligible) | 64.1% | `boamp_linking_stats.csv` |
| KM median survival | 48.2 months | `threshold_sensitivity_summary.csv` |
| Cox C-index (baseline) | 0.6536 / 0.6541* | `threshold_sensitivity_summary.csv` / `sensitivity_comparison.csv` |
| Log-normal AFT AIC | 7,176.5 | `parametric_aic_comparison.csv` |
| SIREN coverage | 660 SIREN / 440 NAME | `boamp_phase2_survival_siren_enriched.csv` |
| Manual validation | 150 drawn, **review NOT executed** | `manual_validation_sample.csv` |

\* The two Cox baseline values (0.6536 vs 0.6541) come from two slightly different model
specifications/runs. Both round consistently; reports keep 0.6541 in the A/B/C comparison table for
internal consistency with that table and 0.654 elsewhere.

---

## 2. Discrepancies found and how they were resolved

### 2.1 Model B / score≥0.50 — GENUINE DATA-LEVEL CONTRADICTION (resolved by user decision)
Two output files described the **same** 497-event / 45.2% conservative population but disagreed:
- `validation_robustness/outputs/threshold_sensitivity_summary.csv`: **KM median 52.8 mo, Cox C 0.645**
- `reports/tables/survival/sensitivity_comparison.csv`: **KM median ∞ (not reached), Cox C 0.6061**

Both values appeared across the reports (phase1 contained *both*: the Model A/B/C table used
0.6061/not-reached, while its own threshold table used 52.8/0.645).

**Root cause (found in code):** the two scripts censored LOW links differently.
`validation_robustness/_build_validation_notebook.py` relabels LOW links to `event=0` but keeps
their observed time → 52.8 / 0.645. `_build_survival_notebook.py` relabelled them AND reset their
time to start→study-end (lines 723-726) → KM median never reached / 0.6061. Both ran correctly; they
encoded two different definitions, so a plain re-run reproduces both.

**Resolution (CODE FIX + re-run, 2026-06-25):** adopt the censor-in-place definition (= the
validation sweep). Edited `_build_survival_notebook.py` to (a) drop the study-end time reset and
(b) use the same reduced 3-covariate Cox as the sweep, then rebuilt and executed
`notebooks/02_survival_modeling_boamp.ipynb`. `sensitivity_comparison.csv` now regenerates
programmatically as **A: 705/48.2/0.6536, B: 497/52.8/0.645**, fully matching
`threshold_sensitivity_summary.csv`. Diff confirmed: only `sensitivity_comparison.csv` changed; all
other survival tables (AIC 7,176.55, Cox HRs) are byte-identical. Reports updated to match. **Closed.**

### 2.2 Placebo / negative-control numbers — STALE (fixed)
Authoritative file `validation_robustness/outputs/placebo_check_summary.csv`:
- real_links: n=705, mean 0.5872, median 0.5576, %≥0.70 = **21.0%**, %≥0.50 = 70.5%
- runner_up: n=**4,814**, mean 0.4388, %≥0.70 = 1.2%
- synthetic_no_buyer: n=705, mean 0.4336, %≥0.70 = 7.1%

Reports carried older-run values (winner mean **0.579**, %≥0.70 = **19.1 / 17.5**, runner-up
n=4,659, synthetic mean 0.425). All updated to the authoritative values. The composite-score mean of
0.587 was independently confirmed by recomputing the mean of `composite_score` over the 705 events
(= 0.5872).

### 2.3 "Cox concordance stays above 0.59" — FACTUALLY WRONG (fixed)
The threshold grid contains Cox C = 0.5346 (score≥0.80) and 0.5503 (score≥0.90), so the claim that
concordance "stays above 0.59" was false. Corrected to "stays above **0.53**" in:
- `internship_report.tex` (robustness bullet)
- `data_quality_report.tex` (threshold sensitivity paragraph)

(`phase1_technical_report.tex` already correctly said "above 0.53".)

### 2.4 Internship by-category event table — PRE-SIREN (fixed)
The per-category event table summed to **697** events (pre-enrichment), not 705. Replaced with the
current breakdown recomputed from `boamp_phase2_survival.csv` (sums to 705).

---

## 3. Verified-correct items (no change needed)
- Raw count **3,181** — correct everywhere (the `wc -l`=3,189 over-count is from multi-line quoted
  CSV fields; `csv.DictReader` = 3,181).
- APPEL_OFFRE **1,933**, eligible **1,100**, events **705**, censored **395**, linking **64.1%**.
- Log-normal AFT **AIC 7,176.5** — correct; **no stale 7,119.8 exists** anywhere in the sources.
- Pre-SIREN numbers **697 / 63.4%** appear only inside labelled before/after comparisons — kept.
- Manual-validation wording ("150 drawn, review not executed, precision/recall unknown") — correct
  and confirmed: the sample CSV's `manual_decision`/`manual_error_type`/`manual_notes` columns are
  empty (0/150).
- Link-quality counts: single-candidate **133**, ambiguous margin<0.05 **265**, strict HC **100** —
  all confirmed against the data.
- SIREN: completed **2026-06-24**, API Recherche d'Entreprises, HIGH-confidence auto-applied,
  unresolved stay NAME-keyed, **not ground truth** — correct.

---

## 4. Remaining limitations / unresolved (need human decision)
1. **Manual validation not executed** → no empirical precision/recall for the linking step.
2. Phase 4 (change-point), trained NLP classifier, DECP contract-level linking, and live-date
   re-scoring remain unimplemented.

### Resolved 2026-06-25 (previously open)
- **sensitivity_comparison.csv** — now regenerated programmatically via the code fix above (was a
  hand-edit). Closed.
- **Cox baseline 0.6536 vs 0.6541** — root cause was the covariate set, *not* the penalizer (both
  already `penalizer=0.1`). The sweep/sensitivity tables use a reduced 3-covariate Cox (baseline
  **0.6536**); the headline full multivariate model is **0.6541**. Both are now labelled as such in
  the reports (phase1 carries a footnote; the sweep CSVs agree at 0.6536). Closed.
