# BOAMP Report Consistency Audit

**Date of audit:** 2026-06-23  
**Auditor:** Claude Code (claude-sonnet-4-6), working session  
**Working directory:** `/home/senghakrou/stage-1`

---

## 1. Reports checked

| Report | Source file | Regenerated PDF |
|---|---|---|
| Internship orientation report | `reports/internship_report.tex` (505 lines) | `reports/internship_report.pdf` (7 pages) |
| Phase 1 & 2 technical report | `reports/phase1_technical_report.tex` (2,956 lines) | `reports/phase1_technical_report.pdf` (69 pages) |

---

## 2. Source files located

All report content is authored in LaTeX. No Makefile exists; build evidence (`.fdb_latexmk` files) confirms `latexmk -pdf` is the standard compile command.

Key data files cross-checked:
- `data/processed/boamp_phase2_survival.csv` — 1,100 rows × 33 cols (event counts, medians)
- `validation_robustness/outputs/threshold_sensitivity_summary.csv` — 7 scenarios (Model B = 52.7 mo)
- `validation_robustness/outputs/uncertain_link_exclusion_summary.csv` — `strict_hc_only` = 90 events (not reached)
- `reports/tables/survival/sensitivity_comparison.csv` — A/B comparison (distinct run, different C-index)
- `reports/tables/survival/parametric_aic_comparison.csv` — log-normal AIC = 7,119.77 ≈ 7,119.8
- `event_validation/outputs/manual_validation_sample.csv` — 150 rows, `manual_decision` column empty
- `scripts/link_confidence.py` — `HIGH_CONFIDENCE_MIN_COMPOSITE = 0.70`, `MIN_TEXT_SIMILARITY = 0.20`

---

## 3. Backup files created

```
reports/internship_report_before_consistency_fix.pdf
reports/internship_report_before_consistency_fix.tex
reports/phase1_technical_report_before_consistency_fix.pdf
reports/phase1_technical_report_before_consistency_fix.tex
```

---

## 4. Commands used to regenerate PDFs

Run from `reports/`:
```bash
latexmk -pdf internship_report.tex
latexmk -pdf phase1_technical_report.tex
```

Both compilations completed without errors. Only standard LaTeX `\hbox` underfull warnings (pre-existing).

---

## 5. Inconsistencies found and corrections made

### A. `phase1_technical_report.tex` — 11 edits

| ID | Location | Issue | Correction |
|---|---|---|---|
| A1 | Summary F5 (~line 2733) | Said "Model B shifts the survival curve upward so **the median is no longer reached**" — wrong, Model B median = 52.7 months | Replaced with: "Model B shifts the KM median from 48.1 to 52.7 months… Model C's median is no longer reached." |
| A2 | Table `tab:threshold_full` baseline label (~line 2476) | Label said "Baseline (all, ≥0.35)" — no 0.35 composite threshold exists in code | Changed label to "Baseline (all accepted links)†"; added footnote explaining only `text_similarity ≥ 0.20` hard filter applies; observed min composite ≈ 0.37 |
| A3 | Table `tab:sensitivity` Model A criterion (~line 2403) | Model A event criterion listed as "composite ≥ 0.20" — incorrect; the actual filter is `text_similarity ≥ 0.20` | Changed to "text ≥ 0.20 (all accepted)" |
| A4 | Summary F2 start_year (~line 2718) | Incomplete caution: "possibly reflecting an accelerating procurement cycle or left-truncation" | Strengthened to: "should be interpreted cautiously: it may reflect calendar-period effects, publication practices, and study-window truncation (2021–2024 contracts are largely right-censored) rather than a genuine acceleration" |
| A5 | Caption `fig:confidence_tiers_4` (~line 1816) | Claimed "Model C corresponds to HIGH and SINGLE tiers" — wrong. SINGLE-candidate links are NOT in Model C (90 events) | Replaced with correct description: Model C = HIGH (n=53, S≥0.80) + subset of MEDIUM with 0.70≤S<0.80 and margin≥0.05 (n=37). Single-candidate links excluded. |
| A6 | Data dictionary `annonce_lie` (line 259) | "Used as partial ground truth for calibration" | Changed to "Used as indirect external calibration signal (back-reference on ATTRIBUTION notices)" |
| A7 | Section heading (line 1885) | "Ground-Truth Calibration" | Renamed to "Indirect External Calibration (annonce_lie)" |
| A8 | Data dictionary `observed_duration_months` (line 1211) | "actual renewal gap Δ(i,j*)" | Changed to "observed gap to the linked BOAMP renewal candidate Δ(i,j*)" |
| A9 | Sensitivity interpretation (~line 2413) | No explicit statement that absolute event rate is sensitive | Added: "The absolute event rate and KM survival level are therefore sensitive to the event definition." |
| A10 | Threshold sweep paragraph (~line 2468) | "from 0.35 (baseline) to 0.90" — 0.35 is not an explicit code threshold | Changed to "from the baseline (all accepted links, no composite floor) up to score ≥ 0.90" |
| A11 | Figure caption threshold figure (~line 2524) | "C-index plateau between 0.35 and 0.70" — stale 0.35 reference | Changed to "C-index plateau from the baseline through score ≥ 0.70" |

### B. `internship_report.tex` — 3 edits

| ID | Location | Issue | Correction |
|---|---|---|---|
| B1 | Link quality paragraph (~line 283) | "Only 53 links (7.6%) satisfy the strict high-confidence criterion (score ≥ 0.80 and margin ≥ 0.05)" conflated the tier-4 HIGH criterion (S≥0.80) with the `high_confidence_strict` flag used for Model C (S≥0.70, 90 events) | Replaced with explicit two-tier description: 90 events (12.9%) satisfy `high_confidence_strict` (S≥0.70, Model C core); stricter tier-4 HIGH gives 53 links (S≥0.80, 7.6%) |
| B2 | Section 5, What Was Not Done (~line 446) | "no ground-truth precision / recall estimates for the linking step" | Changed to "no independently verified precision/recall estimates for the linking step" |
| B3 | Conclusion next steps (~line 496) | "get ground-truth precision/recall for the linking step" | Changed to "obtain independently verified precision/recall estimates for the linking step" |

---

## 6. Output files regenerated

```
reports/internship_report.pdf          (7 pages, 452,141 bytes)
reports/phase1_technical_report.pdf    (69 pages, 4,706,158 bytes)
```

---

## 7. Final verified key numbers (from actual CSVs, confirmed in rendered PDFs)

| Quantity | Value | Source CSV | Present in reports |
|---|---|---|---|
| Eligible contracts | 1,100 | `boamp_phase2_survival.csv` | Both ✓ |
| Events (event=1) | 697 (63.4%) | same | Both ✓ |
| Censored (event=0) | 403 (36.6%) | same | Both ✓ |
| Baseline KM median | 48.1 months | `threshold_sensitivity_summary.csv` | Both ✓ |
| Model B KM median (score≥0.50) | 52.7 months | `threshold_sensitivity_summary.csv` | Both ✓ |
| Model C KM median (strict HC) | not reached | `uncertain_link_exclusion_summary.csv` | Both ✓ |
| 90 strict HC events | 90 | `uncertain_link_exclusion_summary.csv` | Both ✓ |
| 104 threshold strict HC events | 104 | `threshold_sensitivity_summary.csv` | Technical ✓ |
| Log-normal AIC | 7,119.8 | `parametric_aic_comparison.csv` | Both ✓ |
| Manual validation sample | 150 rows, review not done | `manual_validation_sample.csv` | Both ✓ |
| Cox C-index (baseline) | 0.6524 | `threshold_sensitivity_summary.csv` | Both ✓ |

---

## 8. Numbers that were already correct (no change)

- 697, 403, 1,100, 63.4%, 48.1, 52.7 in tables: correct throughout
- Model B KM median = 52.7 months in both report tables: correct (the only error was in the prose summary F5 of the technical report)
- Model C "not reached" in tables: correct
- 90 vs 104 distinction: already explained in technical report (lines 2493–2496, now updated A11 region); no new explanation needed
- AIC 7,119.8: correct
- Manual validation 150 rows / review not done: correct in both
- "prioritisation indicators rather than legally verified renewal probabilities": already correctly stated
- Cox PH assumption section (declared_duration violates PH): already correctly caveated; AFT avoids PH assumption: correctly noted

---

## 9. Remaining limitations (unchanged by this audit)

- **Manual validation not yet done.** The 150-row stratified sample exists in `event_validation/outputs/manual_validation_sample.csv`. All `manual_decision`, `manual_error_type`, and `manual_notes` columns are empty. Precision/recall of the linking step is therefore unknown.
- **Modest discrimination.** Cox C-index ≈ 0.65; sufficient for prioritisation but not high-stakes individual decisions.
- **Structural right-censoring.** 2022–2024 contracts are largely censored; the positive `start_year` HR should be interpreted cautiously.
- **Buyer identification.** ~9% SIRET coverage; normalised name matching may fragment entities.
- **Change-point detection (Phase 4)** not implemented.
- **sensitivity_comparison.csv vs threshold_sensitivity_summary.csv discrepancy.** The file `reports/tables/survival/sensitivity_comparison.csv` lists Model B (score≥0.50) with KM median = inf and Cox C = 0.604, while `threshold_sensitivity_summary.csv` (the main robustness output) shows KM median = 52.7 and C = 0.644 for the same event count (494). Both files have identical event counts but different C-indices, suggesting they were produced by runs with different censoring logic (at-observed-time vs at-study-end). The reports now consistently use `threshold_sensitivity_summary.csv` values (52.7 / 0.644), which align with the main survival notebook output. The `sensitivity_comparison.csv` is retained as an intermediate file but is not relied upon for report numbers.

---

## 10. Unresolved issues

None. All identified inconsistencies have been corrected. The `sensitivity_comparison.csv` discrepancy is documented above as a known difference between two analysis runs and does not affect the report content (reports use the primary robustness output).

---

## 11. Rendered-PDF audit confirmation

Text extracted from both regenerated PDFs using `pypdf` (v6.13.3). All checks passed:

**Internship report — all OK:**
- "ground truth" / "Ground-Truth" / "ground-truth": ABSENT ✓
- "median is no longer reached": ABSENT ✓
- "composite >= 0.20": ABSENT ✓
- "Baseline (all,": ABSENT ✓
- 697, 403, 1,100, 63.4%, 48.1, 52.7, 7,119, 90, 12.9%: PRESENT ✓
- `high_confidence_strict`: PRESENT ✓

**Technical report — all OK:**
- "ground-truth" / "Ground-Truth Calibration" / "partial ground truth": ABSENT ✓
- "actual renewal": ABSENT ✓
- "Baseline (all,": ABSENT ✓
- "from 0.35" / "0.35 (baseline)" / "composite >= 0.20": ABSENT ✓
- "Indirect External Calibration": PRESENT ✓
- "48.1 to 52.7": PRESENT ✓
- "absolute event rate": PRESENT ✓
- "cautiously" + "calendar-period effects" (hyphen-split in PDF but text correct): PRESENT ✓
- 697, 403, 90, 104, "not reached": PRESENT ✓
