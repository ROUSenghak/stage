# BOAMP Renewal Proxy Event — Manual Validation Protocol

**Version:** 1.0  
**Date:** June 2026  
**Dataset:** `boamp_phase2_survival.csv` (1 100 contracts, Pays de la Loire, 2015–2024)  
**Audit sample:** 150 rows — `event_validation/outputs/manual_validation_sample.csv`

---

## 1. Why Validation Is Needed

The survival model predicts whether a public IT procurement contract will be renewed within the BOAMP corpus. The model is trained on a proxy outcome variable (`event`) derived algorithmically from BOAMP publication data. Before reporting model results, we must estimate:

- What fraction of `event=1` labels genuinely correspond to a contract renewal (precision of the proxy).
- What fraction of `event=0` labels correspond to contracts that were actually renewed but not captured (false-negative rate).
- Whether labeling quality differs systematically by technology category, year, or matching confidence tier.

Without this validation, survival model coefficients cannot be reliably interpreted as causal renewal predictors in the internship report.

---

## 2. Why `event` Is a Proxy Variable, Not Ground Truth

The `event` variable does not record a legal or administrative renewal decision. It records whether the matching algorithm identified an **identifiable BOAMP successor notice** for the source contract: a later notice from the same buyer, with similar CPV division and contract object text, appearing within a temporal window consistent with the source contract's declared duration.

This algorithm-derived label has three important limitations:

1. **Under-coverage:** BOAMP data for Pays de la Loire is a sample, not a census. Some successor notices may exist but were not fetched, or the buyer used a different CPV/objet wording that fell below the matching threshold. A `event=0` can therefore represent a genuine non-renewal *or* a renewal missed by the algorithm (plausible censoring).

2. **False matches:** The algorithm uses text similarity and temporal proximity, not legal dossier linkage. Two contracts from the same buyer in the same domain might be matched even if they are unrelated (false positive).

3. **No duration source of truth:** `declared_duration_months` is extracted from a heterogeneous BOAMP field that is often imputed or missing. Temporal window matching therefore carries imprecision.

The correct language for this project is:

- **"identifiable BOAMP successor"** or **"proxy renewal event"** (not "true renewal")
- **"plausible censoring"** for `event=0` where no successor was identified (not "confirmed non-renewal")

---

## 3. How the 150-Row Sample Was Selected

The sample is drawn from `boamp_phase2_survival.csv` (1 100 rows) using stratified random sampling with `RANDOM_SEED=42`. Five priority-ordered strata are filled sequentially (no contract appears twice):

| Stratum | Filter condition | Target n |
|---------|-----------------|----------|
| A — High confidence | `event=1` AND `high_confidence_strict=True` | 20 |
| B — Ambiguous margin | `event=1` AND `score_margin < 0.05` AND `n_candidates > 1` | 20 |
| C — Single candidate | `event=1` AND `single_candidate_match=True` | 15 |
| D — No successor found | `event=0` | 50 |
| E — Remaining event=1 | medium/low confidence, not already sampled | 45 |

Within strata D and E, secondary stratification by `category_label` × `start_year` ensures coverage of rare technology categories and early/late contract cohorts.

**Output file:** `event_validation/outputs/manual_validation_sample.csv`  
**Script:** `event_validation/scripts/build_validation_sample.py`

---

## 4. Manual Review Protocol (Step by Step)

For each row in `manual_validation_sample.csv`:

1. **Open the source record** — click `source_boamp_url` (or search BOAMP for `contract_id` stripped of `BOAMP:`). Tick `boamp_source_record_checked = yes` once viewed.

2. **Read the source contract** — note the buyer name, contract object, CPV code, declared duration, and estimated end date. These are shown in the audit columns for reference but should be verified against the official notice.

3. **If `event=1`** — open the candidate record via `candidate_boamp_url`. Tick `boamp_candidate_record_checked = yes`.
   - Check whether the candidate notice is genuinely a renewal or successor contract for the same buyer and scope.
   - Check whether the candidate publication date is consistent with the source end date.

4. **If `event=0`** — check `nearest_later_notice_id` if present. Open that notice and assess whether it looks like a renewal of the source contract. If yes, this is a potential false negative.

5. **Assign `manual_decision`** (one value from the allowed list below).

6. **Assign `manual_error_type`** (one value from the allowed list below).

7. **Add free-text notes** in `manual_notes` — briefly explain the reason for your decision, especially for uncertain cases.

---

## 5. Decision Taxonomy

### `manual_decision` — Allowed Values

| Value | Meaning |
|-------|---------|
| `credible_renewal` | The candidate notice is clearly a renewal or direct successor of the source contract (same buyer, similar scope, consistent timing). Applies when `event=1`. |
| `doubtful_but_possible` | The link is plausible but uncertain — e.g., scope has shifted, timing is marginal, or the buyer name differs slightly. Applies when `event=1`. |
| `not_credible_false_positive` | The candidate notice is clearly unrelated to the source (different scope, different department, or the match is coincidental). Applies when `event=1`. |
| `plausible_censored` | No successor was found (`event=0`) but the contract was likely renewed — the buyer is active, the domain is recurring, and/or the nearest later notice looks related. |
| `missed_renewal_false_negative` | No successor was identified (`event=0`) but there is strong evidence of a missed renewal — e.g., `nearest_later_notice_id` clearly corresponds to a renewal. |
| `impossible_to_judge` | Cannot assess from available BOAMP data (notice unavailable, buyer name ambiguous, or scope completely unresolvable). |

### `manual_error_type` — Allowed Values

| Value | Meaning |
|-------|---------|
| `true_positive` | Algorithm correctly identified a renewal (`event=1`, manual decision = `credible_renewal`). |
| `false_positive` | Algorithm incorrectly flagged a renewal (`event=1`, manual decision = `not_credible_false_positive`). |
| `true_negative_or_plausible_censored` | Algorithm correctly found no successor, or the non-renewal is genuinely plausible (`event=0`, manual decision = `plausible_censored`). |
| `false_negative` | Algorithm missed a genuine renewal (`event=0`, manual decision = `missed_renewal_false_negative`). |
| `not_applicable` | Case is ambiguous or impossible to judge; cannot be assigned a TP/FP/TN/FN label. |

---

## 6. Difference Between TP, FP, Plausible Censored, and FN

```
Algorithm says event=1 (successor found):
  ├── Successor is genuine renewal         → TRUE POSITIVE  (TP)
  └── Successor is a false match           → FALSE POSITIVE (FP)

Algorithm says event=0 (no successor found):
  ├── Contract was not renewed (or unclear) → TRUE NEGATIVE / PLAUSIBLE CENSORED
  └── Contract WAS renewed, missed by algo  → FALSE NEGATIVE (FN)
```

Note that "true negative" and "plausible censored" are combined here because BOAMP data does not allow us to definitively confirm that a contract was *never* renewed — only that no successor was *identifiable* in the corpus.

---

## 7. Limitations

1. **Observer bias:** Manual review of 150 rows is subjective. The protocol above standardizes decisions but cannot eliminate human judgment variability. Borderline cases should default to `doubtful_but_possible` rather than forcing a binary classification.

2. **BOAMP data gaps:** The corpus covers Pays de la Loire digital IT contracts from 2015 to 2024. Renewals published outside this window, or under different CPV divisions, are systematically uncaptured. FN rates are therefore likely underestimated.

3. **Temporal left-truncation:** Contracts started in 2022–2023 with multi-year durations may not yet have renewal notices in the corpus. High `event=0` rates for recent years reflect censoring, not non-renewal.

4. **Buyer key matching:** The `buyer_key` is derived from a normalised form of `nomacheteur` (buyer name). Name variants (e.g., acronyms, merged agencies) may cause same-buyer notices to be missed by the algorithm.

5. **Sample size:** 150 rows provides approximately ±8% precision on estimated precision/recall at 95% confidence. This is adequate for the internship report but insufficient for regulatory use.

---

## 8. How to Use Validation Results in the Internship Report

After completing the 150-row manual audit:

1. **Compute precision and recall from the audit sample:**
   - Precision (of proxy): `TP / (TP + FP)` — among event=1 labels, what fraction are credible.
   - False-negative rate: `FN / (FN + TN)` — among event=0 labels, what fraction are missed renewals.

2. **Report these as label quality metrics** in the Survival Analysis chapter, before interpreting model coefficients:
   > *"The proxy event variable achieves an estimated precision of X% and a false-negative rate of Y% on the 150-row manual audit sample."*

3. **Use the threshold sensitivity table** (`threshold_sensitivity.csv`) to show how restricting analysis to high-confidence links (`composite_score ≥ 0.70`) improves precision at the cost of sample size.

4. **Use `event_rate_by_category.csv`** to flag categories where the proxy is more or less reliable.

5. **Caveat the survival model results** as conditional on the proxy event definition. Report that hazard ratios reflect "identifiable BOAMP successor" rather than legal contract renewal.

---

## 9. Reproducibility

All output files are regenerated by running one script from the project root:

```bash
cd /home/senghakrou/stage-1
python event_validation/scripts/build_validation_sample.py
```

**Dependencies:** `pandas`, `numpy`, `openpyxl` (all in `requirements.txt`).

**Fixed random seed:** `RANDOM_SEED = 42` — the sample is deterministic given unchanged input CSVs.

**Input files** (must exist before running):
- `data/processed/boamp_phase2_survival.csv`
- `boamp_renewal_linking_quality/outputs/boamp_renewal_candidates.csv`
- `data/processed/boamp_full_clean.csv`

**Expected outputs** in `event_validation/outputs/`:
- `manual_validation_sample.csv` — 150 rows × 32 columns (manual columns blank)
- `validation_summary_metrics.csv` — population-level statistics
- `threshold_sensitivity.csv` — precision/retention at composite_score thresholds
- `event_bias_summary.csv` — event rate by start year
- `event_rate_by_category.csv` — event rate by technology category
- `boamp_event_validation_audit.xlsx` — Excel workbook (6 sheets)

**Verification:**

```bash
python -c "
import pandas as pd
df = pd.read_csv('event_validation/outputs/manual_validation_sample.csv')
print('Rows:', len(df))
print('Events:', df['event'].value_counts().to_dict())
print('Manual cols empty:', df[['manual_decision','manual_error_type']].eq('').all().all())
print('Categories covered:', df['category'].nunique())
"
```
