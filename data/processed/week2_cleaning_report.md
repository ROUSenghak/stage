# Week 2 – Cleaning and Normalization Report

## Scope
- BOAMP full dataset: 3,181 notices (PdL, digital CPV, 2015-2024)
- DECP filtered: 3,039 contracts (PdL, digital CPV, 2015-2024, current version)

## Buyer normalization
Canonical key strategy: **SIRET (14-digit) when valid, normalized name otherwise**.

| Source | Raw unique names | Canonical keys | SIRET-anchored |
|--------|-----------------|----------------|----------------|
| BOAMP  | 525 | 502 | 156 rows (4.9% of notices) |
| DECP   | 278 | 294 | 3,039 rows (100.0% of contracts) |

Name normalization: lowercase, accent stripping, punctuation removal, legal-form suffix removal (e.g. "SARL", "Commune de").
Cross-source bridge saved to `buyer_bridge.csv`.

## Amount cleaning
Flagging rules (values **not deleted**, raw always preserved):
- `flag_amount_zero`: value == 0 → almost certainly an encoding artefact.
- `flag_amount_tiny`: 0 < value < 1 000 EUR → implausible for an IT contract.
- `flag_amount_ceiling`: value ≥ 10 000 000 EUR → likely a framework-agreement ceiling, not the actual contract value.
- `amount_clean`: NaN when any flag is True; original numeric value otherwise.

| Source | Zero | Tiny (<1k) | Ceiling (≥10M) | Clean fill rate |
|--------|------|------------|----------------|-----------------|
| BOAMP  | 1 | 9 | 53 | 41.1% |
| DECP   | 31 | 20 | 23 | 93.1% |

**Remaining missing values** in amount_clean come from original NaN fields and are **not imputed at this stage** (Week-3 modeling will use median-by-segment imputation for covariates that need a numeric value).

## Duration cleaning
Flagging rule: `flag_duration_suspect` = 1 when `dureeMois` / `duration_months` outside [1, 120] months.
Suspect values are set to NaN in `duration_clean` but kept raw.

| Source | Suspect flags | Clean fill rate |
|--------|---------------|-----------------|
| BOAMP  | 12 | 47.3% |
| DECP   | 6  | 99.2% |

## Taxonomy tagging (10 categories)
CPV-prefix match first; keyword-in-objet fallback.  Full taxonomy: `taxonomy.csv`.

| Category | BOAMP | DECP |
|----------|-------|------|
| CAT01 | 88 | 608 |
| CAT02 | 167 | 1321 |
| CAT03 | 63 | 337 |
| CAT04 | 80 | 581 |
| CAT05 | 7 | 28 |
| CAT06 | 10 | 14 |
| CAT07 | 28 | 110 |
| CAT08 | 8 | 15 |
| CAT09 | 3 | 2 |
| CAT10 | 9 | 23 |
| CAT_UNKNOWN | 37 | 0 |

## Known limitations
1. BOAMP SIRET-anchored buyer_key coverage is 4.9% of notices (156 of 3,181 have a `SIRET:`-prefixed canonical key). The `buyer_siret` API field is filled for 9.1% of notices but includes SIREN-only and partially-invalid identifiers that do not pass validation. Legacy notices (pre-2024) carry no SIRET; only eForms notices (2024+) do reliably. Name-based matching is imprecise for common institutional names (e.g. "SDIS 44").
2. Amount ceilings (≥10 M) for framework agreements cannot be distinguished automatically without human review.
3. Taxonomy tagging via CPV prefix is deterministic but will miss contracts with generic CPV codes (e.g. 72000000) not rescued by keyword fallback.
