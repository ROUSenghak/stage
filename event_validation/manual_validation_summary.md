# Manual Validation of the BOAMP Renewal Proxy Event — Summary

**Date:** 2026-07-02 · **Dataset audited:** `data/processed/boamp_phase2_survival.csv` (W=6 rerun: 1,210 eligible, 665 events)
**Sample:** 150 stratified cases (100 linked pairs, 50 unlinked sources), seed 42
**Labeled file:** `event_validation/outputs/manual_validation_audit_labeled.csv` · Workbook: `event_validation/outputs/boamp_event_validation_audit.xlsx` (sheet `Audit_Results`)

## Method (honest scope)

Each case was reviewed against the **full official BOAMP notice records** (verbatim
API records held in the repository, extracted per case into the workbook's
`BOAMP_Raw_Records` sheet): buyer identity (name, SIRET/SIREN), the complete
`objet` text on both sides, CPV codes, procedure and market type, dates and gap
vs. declared duration, all four score components, the margin, and the runner-up
candidates. For every **unlinked** source, an active counter-search for missed
renewals was run over the full 3,181-notice corpus: all later `APPEL_OFFRE`
notices from the same buyer key *and* from fuzzy-similar buyer names
(token-sort ≥ 80), ranked by Sentence-Transformer semantic similarity, plus a
corpus-wide semantic top-3 regardless of buyer to catch buyer-name
fragmentation. Wording differences alone were never grounds for rejection; the
question asked was whether buyer, service, CPV family, timing and procurement
context indicate the **same recurring need**. Live boamp.fr pages are
JS-rendered and could not be fetched in this environment; the local records
*are* the official notice contents. Labels were assigned by an AI-assisted
reviewer (Claude); borderline cases were marked UNCERTAIN rather than forced.

**This is a manual audit estimate on a stratified sample — not population-level
ground truth.** There is no legal renewal register; even a "TP" label means
*credible* renewal, not certified renewal.

## Results

| Quantity | Value |
|---|---|
| Linked pairs audited | 100 → **TP 14 · FP 82 · UNCERTAIN 4** |
| Unlinked sources audited | 50 → **TN 41 · FN 6 · UNCERTAIN 3** |
| Precision (raw sample, decided cases) | **14.6%** (14/96) |
| Precision (stratum-weighted to the 665-event population) | **≈ 8.8%** |
| False-positive rate among decided linked pairs | 85.4% |
| Missed-renewal rate among decided unlinked | **12.8%** (6/47) → ≈ 70 of 545 censored |
| Proxy recall (population-scaled, highly approximate) | ≈ 0.46 |
| Uncertainty rate | 4.7% (7/150) |

### Precision by stratum / signal

| Slice | Precision (decided) |
|---|---|
| HIGH tier (composite ≥ 0.70) | **0.50** (11/22) |
| `high_confidence_strict` flag | **0.50** (10/20) |
| MEDIUM tier (0.50–0.70) | 0.09 (3/34) |
| LOW tier (< 0.50) | **0.00** (0/40) |
| Text similarity ≥ 0.80 | **1.00** (11/11) |
| Text similarity 0.50–0.80 | 0.12 |
| Text similarity < 0.50 | 0.00 |
| CPV exact 8-digit match | 0.41 |
| CPV weak/zero | 0.03 |
| NAME buyer key | 0.16 |
| SIREN buyer key | 0.14 |

### Main causes of false positives

1. **Different need, same buyer, right timing.** The algorithm links the *best*
   same-buyer candidate near the estimated end date; for large buyers (Nantes
   Métropole, Région, CHU…) that candidate is usually a *different* IT
   procurement (e.g. Business-Objects maintenance → contact-management tool).
2. **Generic CPV codes** (48000000, 72000000) give a perfect CPV component to
   unrelated pairs, lifting composites above 0.70 (several strict-flag FPs).
3. **Low text-similarity floor (0.20)**: below ≈ 0.5 text similarity, no audited
   link was a credible renewal.
4. **Buyer-key over-merge** (2 cases): Conseil régional and Préfecture de région
   merged into one key, linking across distinct legal entities.

### Main causes of false negatives

1. **Early renewal outside the ±6-month window** — declared durations are
   administrative ceilings, so real re-tenders come months/years before the
   estimated end (e.g. infogérance renewed at month 34 of a 48-month ceiling).
2. **Buyer renamed or restructured** (E.C.A.S. gendarmerie → COMSOPGN;
   SM Mégalis → Syndicat mixte Gigalis).
3. **Annual cycles missed by weeks** (identical annual notice published 3 weeks
   after the window closed).
4. **Declared duration far below the true cycle** (12-month declared, re-tender
   at month 39).

## Implications for the survival analysis

The proxy `event` variable is **not validated at the baseline definition**: at
composite < 0.50 essentially all audited links are false, and the audited
precision of the full 665-event set is roughly 9–15%. Only the high-text-
similarity core (text ≥ 0.80: 11/11 correct; strict flag: ~50%) behaves like a
true renewal signal. Model A results (KM median 50.1 months, Cox C 0.6317)
should therefore be read as describing *the timing of algorithm-identifiable
same-buyer re-publications*, not validated renewals. Conservative definitions
(Model B and stricter) are closer to a defensible event but are underpowered.
Recall is approximate (≈ 0.46) because censored contracts also hide ≈ 13%
missed renewals — the two errors do **not** cancel: they change *which*
contracts count as renewed.

**Recommended next steps:** raise the hard text-similarity floor (≥ 0.5, ideally
≥ 0.65), stop scoring generic CPV codes as exact matches, widen or de-anchor the
temporal window from the declared-duration ceiling, and re-estimate the survival
models on the re-linked events; re-audit a fresh sample after re-linking.
