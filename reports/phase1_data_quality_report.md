# Phase 1 Data Quality Report
## BOAMP Procurement Renewal Linking — Pays-de-la-Loire (2015–2024)

**Prepared:** 2026-06-17  
**Dataset:** `data/processed/boamp_phase2_survival.csv`  
**Study period:** 2015-01-01 to 2024-12-31  
**Scope:** Digital/ICT contracts (CPV divisions 48, 72, 32, 35), Pays-de-la-Loire (departments 44, 49, 53, 72, 85)

---

## 1. Corpus Overview

### 1.1 Raw corpus (all notice types)

| Notice type | Count | % |
|---|---|---|
| APPEL_OFFRE (calls for tender) | 1,933 | 60.6% |
| ATTRIBUTION (award notices) | 1,086 | 34.1% |
| RECTIFICATIF (corrections) | 150 | 4.7% |
| PRE-INFORMATION | 7 | 0.2% |
| MODIFICATION | 5 | 0.2% |
| INTENTION_CONCLURE | 4 | 0.1% |
| PERIODIQUE | 1 | 0.0% |
| **Total** | **3,188** | 100% |

Raw data fetched via the BOAMP Opendatasoft Explore API (`scripts/task1b_boamp_full_fetch.py`), stored as 465 JSON files in `data/raw/boamp_full/`. All notices published 2015–2024 in the five PdL departments with digital-sector CPV codes were retained.

### 1.2 Field coverage

| Field | BOAMP fill rate | Notes |
|---|---|---|
| `objet` (contract description) | 100% | Primary NLP input for linking |
| `nomacheteur` (buyer name) | 100% | Free-text; 525 raw unique names → 475 canonical keys |
| CPV code (`cpv_principal`) | 98.1% | Missing 62 notices; missing filled from supplementary lot CPVs where possible |
| `type_procedure` | 92.9% | Covers 8 procedure types |
| Amount (`amount_eur`) | 43.0% | See §3.2 |
| Duration (`duration_months`) | 47.7% | See §3.3 |
| Buyer SIRET (`buyer_siret`) | 9.1% | Only eForms notices (2024+) carry it reliably |

---

## 2. Source Comparison: BOAMP vs DECP

Both BOAMP and DECP (Données Essentielles de la Commande Publique) were evaluated. BOAMP is the sole primary source for this study for the following reasons:

| Field | BOAMP | DECP | Decision |
|---|---|---|---|
| Study period coverage | 2015–2024 | 2018–2024 | **BOAMP** — full period required |
| Notice type granularity (AO vs award) | Yes | No | **BOAMP** — survival analysis needs this |
| Contract description (`objet`) | Rich free text, 100% | Terse, 99.9% | **BOAMP** — richer for NLP |
| Linked notices (`annonce_lie`) | 34.9% | No | **BOAMP** — key for renewal linking |
| Buyer SIRET | 9.1% | 100% | DECP better |
| Amount (EUR) | 43.0% | 95.6% | DECP better |
| Duration (months) | 47.7% | 99.4% | DECP better |

DECP was explored as an enrichment source but not included in the Phase 2 handoff because no reliable cross-source contract-level join key exists for pre-2022 BOAMP notices (no SIRET). Cross-source linking is deferred to Phase 3.

---

## 3. Cleaning Pipeline

### 3.1 Buyer key normalization

The canonical buyer key `buyer_key` follows the rule:

- `SIRET:XXXXXXXXXXXXXXX` when a valid 14-digit SIRET is available
- `NAME:ϕ(name)` otherwise, where ϕ applies: lowercase → NFD accent removal → punctuation/whitespace stripping → legal-form suffix removal (e.g., "Commune de", "SARL")

| Metric | Value |
|---|---|
| Raw unique buyer names | 525 |
| Canonical buyer keys | 475 |
| Keys with SIRET (unique buyer level) | 28 (5.9% of 475 keys) |
| Notices with SIRET-identified buyer | 87 (2.7% of 3,188 notices) |
| Keys with name-based identifier | 447 (94.1%) |

**Risk:** Name-based keys fragment buyers with typographic variants (e.g., "Ville de Nantes" vs "V. de Nantes"). This is the primary source of false negatives in renewal linking. Cross-buyer linking is not in scope for Phase 1.

### 3.2 Amount cleaning

Raw amounts were not deleted; instead, three quality flags were added:

| Flag | Condition | BOAMP count |
|---|---|---|
| `flag_amount_zero` | value == 0 | 1 |
| `flag_amount_tiny` | 0 < value < 1,000 EUR | 9 |
| `flag_amount_ceiling` | value ≥ 10,000,000 EUR | 53 |

`amount_clean` is set to NaN when any flag is True; otherwise equals the original numeric value.  
**Clean fill rate:** 41.1% (BOAMP) vs 93.1% (DECP).  
The low BOAMP fill rate reflects the mandatory reporting shift to eForms in 2024; pre-2024 BOAMP notices carry amounts only on award notices, not calls for tender.

### 3.3 Duration cleaning

`flag_duration_suspect` = 1 for values outside [1, 120] months (implausible range).  
12 notices flagged; `duration_clean` is set to NaN for those, raw value preserved.  
**Clean fill rate:** 47.3% of all notices; 52.7% of APPEL_OFFRE notices.

69.5% of available durations cluster at 12, 24, 36, or 48 months — this is an administrative reporting ceiling, not an empirical lifetime distribution, and should not be used as the survival time. The model survival time is `observed_duration_months` (gap to renewal or to study end), not `declared_duration_months`.

**Imputation rule for missing duration:** 23.4% of eligible APPEL_OFFRE notices have no declared duration. These are imputed to a default of **48 months**. The boolean flag `dur_was_imputed` marks these rows in the survival dataset.

### 3.4 Technology taxonomy

10 technology categories (CAT01–CAT10) plus "Unknown" are assigned via CPV prefix match, with keyword-in-objet fallback. Defined in `data/processed/taxonomy.csv`.

| Category | BOAMP count |
|---|---|
| CAT01 — IT Services & Consulting | 88 |
| CAT02 — Software & Applications | 167 |
| CAT03 — Telecom & Networks | 63 |
| CAT04 — Cybersecurity | 80 |
| CAT05 — Digital Workplace | 7 |
| CAT06 — Data & AI | 10 |
| CAT07 — IT Hardware & Equipment | 28 |
| CAT08 — IT Maintenance & Support | 8 |
| CAT09 — Cloud & Infrastructure | 3 |
| CAT10 — GIS & Mapping | 9 |
| Unknown | 37 |

---

## 4. Renewal Linking

### 4.1 Eligibility funnel

| Step | Count |
|---|---|
| Total BOAMP notices | 3,188 |
| APPEL_OFFRE notices | 1,933 |
| Ineligible (estimated end date after 2024-12-31) | 833 |
| **Eligible source contracts** | **1,100** |
| Linked renewals found (event = 1) | 697 (63.36%) |
| Right-censored (event = 0) | 403 (36.64%) |

A contract is eligible if its estimated end date `ê_i = start_date + declared_duration_months` falls within the study period. Contracts with `ê_i > 2024-12-31` are excluded from the denominator; they are not treated as censored (the renewal window has not opened yet).

### 4.2 Algorithm summary

For each eligible source contract `i`, candidates `j` are identified by the same `buyer_key`. Each candidate pair is scored with a composite formula:

```
S(i,j) = 0.40 × text_similarity
        + 0.25 × cpv_match_score
        + 0.20 × temporal_score
        + 0.15 × buyer_match_score
```

**Hard filters:** `text_similarity ≥ 0.20`; gap δ(i,j) ∈ [6, 72] months.  
**Best match:** the candidate with the highest composite score is selected; `event = 1` if composite ≥ 0.0 after filtering.

Text similarity uses `paraphrase-multilingual-MiniLM-L12-v2` (Sentence-Transformers, 384-dim) cosine similarity on normalized `objet` text.

### 4.3 Baseline comparison

| Method | Linked | Eligible | Rate |
|---|---|---|---|
| Jaccard + buyer×CPV hard groupby (baseline) | 219 | 1,933 | 11.3% |
| TF-IDF cosine + buyer-only groupby | 279 | 1,100 | 25.4% |
| Sentence-Transformers (this study) | 697 | 1,100 | **63.4%** |

---

## 5. Linking Rate by Technology Category

| Category | Eligible (n) | Linked | Event rate |
|---|---|---|---|
| IT Services & Consulting | 312 | 211 | 67.6% |
| Software & Applications | 209 | 148 | 70.8% |
| Telecom & Networks | 204 | 120 | 58.8% |
| Cybersecurity | 121 | 76 | 62.8% |
| Unknown | 108 | 58 | 53.7% |
| Digital Workplace & Collaboration | 45 | 29 | 64.4% |
| Data & AI | 34 | 14 | 41.2% |
| IT Maintenance & Support | 22 | 14 | 63.6% |
| IT Hardware & Equipment | 21 | 10 | 47.6% |
| Cloud & Infrastructure | 19 | 13 | 68.4% |
| GIS & Mapping | 5 | 4 | 80.0% |
| **Total** | **1,100** | **697** | **63.4%** |

The lowest event rates are in **Data & AI** (41.2%) and **IT Hardware & Equipment** (47.6%). These categories tend to have shorter, more ad-hoc procurement cycles and may be systematically underrepresented in the linked set.

### 5.1 Failure mode analysis

Among the 403 unlinked eligible contracts:

| Failure reason | Count | % of unlinked |
|---|---|---|
| NO_TEMPORAL_PARTNER | 339 | 84.1% |
| TEXT_MISMATCH | 40 | 9.9% |
| CPV_MISMATCH | 24 | 6.0% |

**NO_TEMPORAL_PARTNER** (84.1%) means no candidate from the same buyer fell within the ±12-month temporal window around the expected renewal date. This is a structural ceiling: the buyer may not have renewed, or the renewal was published outside the study window. It cannot be improved by threshold tuning.

**TEXT_MISMATCH** (9.9%) and **CPV_MISMATCH** (6.0%) identify cases where a temporal partner existed but failed the similarity or CPV threshold. These are recoverable at the cost of increased false positives.

---

## 6. Confidence Tiers

Links are stratified into three confidence tiers based on composite score:

| Tier | Composite threshold | Count | % of linked |
|---|---|---|---|
| HIGH | ≥ 0.70 | 181 | 26.0% |
| MEDIUM | 0.50 – 0.70 | 347 | 49.8% |
| LOW | < 0.50 | 169 | 24.2% |

For Phase 2 sensitivity analysis, a conservative scenario drops LOW-tier links to `event = 0` (528 events instead of 697). The recommended primary analysis uses all 697 events with composite score as a continuous covariate.

---

## 7. Known Biases and Limitations

1. **No ground truth.** No external validation set exists for BOAMP renewal links. Calibration uses `annonce_lie` back-references (68.2% recall on same-contract pairs) as a proxy, but systematic precision estimation is not possible.

2. **Buyer fragmentation.** 94.1% of buyer keys are name-based. A single public entity with naming variants across years will appear as multiple buyer keys, blocking valid links. This is the primary source of false negatives.

3. **Duration imputation bias.** 23.4% of AO have missing durations imputed to 48 months. The estimated end date for those contracts is a rough guess; the temporal score and eligibility determination are less reliable for this subset. The `dur_was_imputed` flag identifies them.

4. **Right-censoring may be informative.** Unlinked contracts (event = 0) may systematically differ from linked contracts on observables (CPV, amount, buyer size). A formal test (logistic regression: event ~ covariates) is recommended before Phase 2 modeling.

5. **Scope limitation.** Only BOAMP is used; DECP would improve buyer SIRET coverage and contract amounts. A cross-source join is deferred to Phase 3.

6. **False positives among LOW-tier links.** 169 links (24.2% of events) have composite < 0.50; among these, 89 have text similarity between 0.20 and 0.30, which is below the calibrated 0.30 threshold for same-contract pairs. These should be treated as uncertain in Phase 2 sensitivity analyses.

---

## 8. Phase 2 Handoff Dataset Summary

**File:** `data/processed/boamp_phase2_survival.csv`  
**Rows:** 1,100 (one per eligible APPEL_OFFRE notice)  
**Columns:** 27

Key survival columns:

| Column | Description |
|---|---|
| `event` | 1 = renewal found; 0 = censored |
| `observed_duration_months` | Survival time (gap to renewal for event=1; gap to 2024-12-31 for event=0) |
| `start_date` | Contract start (award date when available, else publication date) |
| `declared_duration_months` | Administrative declared duration (covariate, not survival time) |
| `dur_was_imputed` | True if declared_duration was missing and imputed to 48 months |
| `composite_score` | Linking confidence (non-null for event=1 only) |
| `category_label` | Technology category (11 values including Unknown) |
| `cpv_div2` | 2-digit CPV division |
| `amount_clean` | Contract amount EUR (43% fill; use with missing indicator) |
