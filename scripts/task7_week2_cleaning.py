"""TASK 7 — Week 2: Cleaning, Normalization, and Taxonomy Tagging.

Reads the flat outputs from Tasks 1 and 3 (BOAMP + DECP), applies documented
cleaning rules, builds canonical buyer keys, assigns taxonomy labels, and
writes two analysis-ready datasets that feed all later modeling steps.

Cleaning rules applied
----------------------
Buyer normalization
  1. Canonical key = SIRET (14 digits) when present and valid.
  2. Fallback = normalized name key: lowercase, stripped accents, collapsed
     whitespace, punctuation removed, legal-form suffixes dropped.
  3. A cross-source buyer bridge table is written for audit.

Amount cleaning (BOAMP: amount_eur; DECP: montant)
  Rules based on profiling deep-dives (Tasks 2 / 3):
  - flag_amount_zero   : value == 0
  - flag_amount_tiny   : 0 < value < 1 000 EUR
  - flag_amount_ceiling: value >= 10 000 000 EUR
  - amount_clean: NaN when any flag is True, else original value.
  Rationale: zero and tiny values are almost certainly encoding artefacts;
  >=10 M may be framework-agreement ceilings, not real contract values.
  Both the raw and cleaned columns are kept — no data is deleted.

CPV normalization
  - Strip check digit (suffix after '-').
  - Keep only the first 8 digits.
  - Derive cpv_div2 (first 2 digits) and cpv_class4 (first 4 digits).

Duration normalization (DECP only at this stage)
  - Clamp dureeMois to [1, 120] months; values outside are flagged.
  - BOAMP duration_months already produced by Task 1.

Taxonomy tagging
  - Assigns category_id + category_label from data/processed/taxonomy.csv.
  - Logic: CPV prefix match first, then keyword search in objet field.
  - Returns the best single match (first CPV hit wins; first keyword hit wins
    when CPV match is absent; CAT_UNKNOWN otherwise).

Outputs
-------
  data/processed/boamp_clean.csv     — BOAMP 500-sample, cleaned (legacy reference only;
                                        for the full dataset see task_boamp_full_clean.py)
  data/processed/decp_clean.csv      — DECP analysis-ready (3,039 rows)
  data/processed/buyer_bridge.csv    — canonical buyer keys, both sources
  data/processed/week2_cleaning_report.md  — short data-quality report
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from utils import PROCESSED_DIR

# ── Constants ────────────────────────────────────────────────────────────────

AMOUNT_TINY_THRESHOLD = 1_000        # EUR
AMOUNT_CEILING_THRESHOLD = 10_000_000  # EUR
DURATION_MIN_MONTHS = 1
DURATION_MAX_MONTHS = 120

LEGAL_SUFFIXES = re.compile(
    r"\b(sarl|sas|sa|sasu|eurl|sci|scp|scop|inc|llc|gmbh|bv|nv|spa"
    r"|commune de|mairie de|ville de|departement de|region de"
    r"|metropole de|communaute de|syndicat de|sdis|chu|chru|ch\b"
    r"|conseil departemental|conseil regional"
    r"|université de|universite de|centre hospitalier"
    r"|etablissement public|groupement de commandes)\b",
    flags=re.IGNORECASE,
)


# ── Buyer normalization ──────────────────────────────────────────────────────

def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = name.lower()
    name = strip_accents(name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = LEGAL_SUFFIXES.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def canonical_buyer_key(siret: str | None, name: str | None) -> str:
    """SIRET-first canonical key, name-key fallback."""
    if isinstance(siret, str) and re.fullmatch(r"\d{14}", siret.strip()):
        return f"SIRET:{siret.strip()}"
    norm = normalize_name(name or "")
    return f"NAME:{norm}" if norm else "UNKNOWN"


# ── CPV normalization ────────────────────────────────────────────────────────

def clean_cpv(raw) -> str | None:
    """Normalize a raw CPV value to its 8-digit main code (or None).

    Robust to floats, ints, strings and ``"…\\.0"`` artifacts; preserves the
    8-digit width so leading zeros are not lost. The 9th digit after a dash (or
    a 9-digit no-dash value) is a check digit and is dropped.

    Examples
    --------
    ``72000000`` / ``72000000.0`` / ``"72000000-9"`` / ``72000000-9`` → ``"72000000"``
    ``3000000`` (leading zero lost on int storage)                    → ``"03000000"``
    """
    if pd.isna(raw):
        return None
    # Drop the dash check digit first, then any float artifact like ".0".
    code = str(raw).strip().split("-")[0].strip()
    if code.endswith(".0"):
        code = code[:-2]
    digits = re.sub(r"\D", "", code)
    if not digits:
        return None
    # A 9-digit value carries the check digit without a dash → keep first 8.
    digits = digits[:8]
    # CPV codes are 8 digits; a 7-digit value lost a leading zero on numeric storage.
    if len(digits) == 7:
        digits = "0" + digits
    return digits if len(digits) >= 2 else None


# ── Amount cleaning ──────────────────────────────────────────────────────────

def apply_amount_flags(series: pd.Series) -> pd.DataFrame:
    amt = pd.to_numeric(series, errors="coerce")
    zero = amt == 0
    tiny = (amt > 0) & (amt < AMOUNT_TINY_THRESHOLD)
    ceil = amt >= AMOUNT_CEILING_THRESHOLD
    clean = amt.where(~(zero | tiny | ceil))
    return pd.DataFrame({
        "amount_raw": amt,
        "flag_amount_zero": zero.astype(int),
        "flag_amount_tiny": tiny.astype(int),
        "flag_amount_ceiling": ceil.astype(int),
        "amount_clean": clean,
    })


# ── Duration cleaning ────────────────────────────────────────────────────────

def apply_duration_flags(series: pd.Series) -> pd.DataFrame:
    dur = pd.to_numeric(series, errors="coerce")
    flag = (~dur.between(DURATION_MIN_MONTHS, DURATION_MAX_MONTHS, inclusive="both")
            & dur.notna()).astype(int)
    clean = dur.where(dur.between(DURATION_MIN_MONTHS, DURATION_MAX_MONTHS,
                                   inclusive="both"))
    return pd.DataFrame({
        "duration_raw": dur,
        "flag_duration_suspect": flag,
        "duration_clean": clean,
    })


# ── Taxonomy tagging ─────────────────────────────────────────────────────────

def build_taxonomy_matcher(taxonomy: pd.DataFrame):
    """Returns a function (cpv: str, objet: str) -> (cat_id, cat_label)."""
    # Pre-compile CPV prefix lists and keyword patterns per category.
    entries = []
    for _, row in taxonomy.iterrows():
        prefixes = [p.strip() for p in str(row["cpv_prefixes"]).split(",") if p.strip()]
        kw_pattern = re.compile(
            "|".join(re.escape(k.strip()) for k in str(row["keywords"]).split(",")
                     if k.strip()),
            re.IGNORECASE,
        )
        entries.append((row["category_id"], row["category_label"], prefixes, kw_pattern))

    def match(cpv, objet) -> tuple[str, str]:
        cpv_str = str(cpv or "")
        # CPV match first: longest prefix wins.
        best_id, best_label, best_len = "CAT_UNKNOWN", "Unknown", 0
        for cat_id, cat_label, prefixes, _ in entries:
            for p in prefixes:
                if cpv_str.startswith(p) and len(p) > best_len:
                    best_id, best_label, best_len = cat_id, cat_label, len(p)
        if best_len > 0:
            return best_id, best_label
        # Keyword fallback on objet.
        objet_str = str(objet or "")
        for cat_id, cat_label, _, kw_pattern in entries:
            if kw_pattern.search(objet_str):
                return cat_id, cat_label
        return "CAT_UNKNOWN", "Unknown"

    return match


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    taxonomy = pd.read_csv(PROCESSED_DIR / "taxonomy.csv", dtype=str)
    matcher = build_taxonomy_matcher(taxonomy)

    # ── BOAMP ──────────────────────────────────────────────────────────────
    boamp = pd.read_csv(
        PROCESSED_DIR / "boamp_sample_flat.csv",
        dtype={"buyer_siret": str, "cpv_principal": str},
    )

    # Buyer key
    boamp["buyer_key"] = [
        canonical_buyer_key(s, n)
        for s, n in zip(boamp["buyer_siret"], boamp["nomacheteur"])
    ]

    # CPV
    boamp["cpv_clean"] = boamp["cpv_principal"].map(clean_cpv)
    boamp["cpv_div2"] = boamp["cpv_clean"].str[:2]
    boamp["cpv_class4"] = boamp["cpv_clean"].str[:4]

    # Amount
    amt_flags = apply_amount_flags(boamp["amount_eur"])
    boamp = pd.concat([boamp, amt_flags], axis=1)

    # Duration (already in months from Task 1)
    dur_flags = apply_duration_flags(boamp["duration_months"])
    boamp = pd.concat([boamp, dur_flags.rename(columns={
        "duration_raw": "duration_raw_boamp",
        "flag_duration_suspect": "flag_duration_suspect",
        "duration_clean": "duration_clean",
    })], axis=1)

    # Taxonomy
    tags = [matcher(c, o) for c, o in zip(boamp["cpv_clean"], boamp["objet"])]
    boamp["category_id"] = [t[0] for t in tags]
    boamp["category_label"] = [t[1] for t in tags]

    boamp_out = PROCESSED_DIR / "boamp_clean.csv"
    boamp.to_csv(boamp_out, index=False)

    # ── DECP ───────────────────────────────────────────────────────────────
    decp = pd.read_csv(
        PROCESSED_DIR / "decp_sample_flat.csv",
        dtype={"acheteur_id": str, "codeCPV": str},
    )

    # Buyer key
    decp["buyer_key"] = [
        canonical_buyer_key(s, n)
        for s, n in zip(decp["acheteur_id"], decp["acheteur_nom"])
    ]

    # CPV
    decp["cpv_clean"] = decp["codeCPV"].map(clean_cpv)
    decp["cpv_div2"] = decp["cpv_clean"].str[:2]
    decp["cpv_class4"] = decp["cpv_clean"].str[:4]

    # Amount
    amt_flags_d = apply_amount_flags(decp["montant"])
    decp = pd.concat([decp, amt_flags_d], axis=1)

    # Duration
    dur_flags_d = apply_duration_flags(decp["dureeMois"])
    decp = pd.concat([decp, dur_flags_d.rename(columns={
        "duration_raw": "duration_raw_decp",
        "flag_duration_suspect": "flag_duration_suspect",
        "duration_clean": "duration_clean",
    })], axis=1)

    # Taxonomy
    tags_d = [matcher(c, o) for c, o in zip(decp["cpv_clean"], decp["objet"])]
    decp["category_id"] = [t[0] for t in tags_d]
    decp["category_label"] = [t[1] for t in tags_d]

    decp_out = PROCESSED_DIR / "decp_clean.csv"
    decp.to_csv(decp_out, index=False)

    # ── Buyer bridge ───────────────────────────────────────────────────────
    boamp_buyers = (
        boamp[["buyer_key", "buyer_siret", "nomacheteur"]]
        .drop_duplicates("buyer_key")
        .rename(columns={"buyer_siret": "boamp_siret", "nomacheteur": "boamp_name"})
        .assign(source="BOAMP")
    )
    decp_buyers = (
        decp[["buyer_key", "acheteur_id", "acheteur_nom"]]
        .drop_duplicates("buyer_key")
        .rename(columns={"acheteur_id": "decp_siret", "acheteur_nom": "decp_name"})
        .assign(source="DECP")
    )
    bridge = pd.merge(
        boamp_buyers, decp_buyers, on="buyer_key", how="outer", suffixes=("_b", "_d")
    )
    bridge_out = PROCESSED_DIR / "buyer_bridge.csv"
    bridge.to_csv(bridge_out, index=False)

    # ── Stats for report ───────────────────────────────────────────────────
    n_b = len(boamp)
    n_d = len(decp)

    b_buyer_before = boamp["nomacheteur"].nunique()
    b_buyer_after = boamp["buyer_key"].nunique()
    d_buyer_before = decp["acheteur_nom"].nunique()
    d_buyer_after = decp["buyer_key"].nunique()

    b_siret_keys = (boamp["buyer_key"].str.startswith("SIRET:")).sum()
    d_siret_keys = (decp["buyer_key"].str.startswith("SIRET:")).sum()

    b_amt_zero = int(boamp["flag_amount_zero"].sum())
    b_amt_tiny = int(boamp["flag_amount_tiny"].sum())
    b_amt_ceil = int(boamp["flag_amount_ceiling"].sum())
    b_amt_clean_rate = round(100 * boamp["amount_clean"].notna().mean(), 1)

    d_amt_zero = int(decp["flag_amount_zero"].sum())
    d_amt_tiny = int(decp["flag_amount_tiny"].sum())
    d_amt_ceil = int(decp["flag_amount_ceiling"].sum())
    d_amt_clean_rate = round(100 * decp["amount_clean"].notna().mean(), 1)

    b_dur_suspect = int(boamp["flag_duration_suspect"].sum())
    d_dur_suspect = int(decp["flag_duration_suspect"].sum())

    b_cat = boamp["category_id"].value_counts().to_dict()
    d_cat = decp["category_id"].value_counts().to_dict()

    # ── Print summary ──────────────────────────────────────────────────────
    print("=== TASK 7 summary ===")
    print(f"\nSaved BOAMP clean : {boamp_out}  ({n_b} rows)")
    print(f"Saved DECP clean  : {decp_out}  ({n_d} rows)")
    print(f"Saved buyer bridge: {bridge_out}  ({len(bridge)} unique keys)")

    print("\n── Buyer normalization ──")
    # NOTE: SIRET-anchored count is per-row not per unique key for DECP (every row
    # carries a SIRET), so we report it as rows rather than unique keys.
    print(f"  BOAMP: {b_buyer_before} raw names → {b_buyer_after} canonical keys"
          f" ({b_siret_keys} SIRET-anchored rows, {n_b - b_siret_keys} name-anchored rows)")
    print(f"  DECP : {d_buyer_before} raw names → {d_buyer_after} canonical keys"
          f" ({d_siret_keys} SIRET-anchored rows / {n_d} total rows)")

    print("\n── Amount cleaning ──")
    print(f"  BOAMP: zero={b_amt_zero}, tiny<1k={b_amt_tiny}, ceiling≥10M={b_amt_ceil}"
          f"  →  clean fill rate {b_amt_clean_rate}%")
    print(f"  DECP : zero={d_amt_zero}, tiny<1k={d_amt_tiny}, ceiling≥10M={d_amt_ceil}"
          f"  →  clean fill rate {d_amt_clean_rate}%")

    print("\n── Duration cleaning ──")
    print(f"  BOAMP: suspect values (outside 1–120 months): {b_dur_suspect}")
    print(f"  DECP : suspect values (outside 1–120 months): {d_dur_suspect}")

    print("\n── Taxonomy tagging ──")
    print(f"  BOAMP: {b_cat}")
    print(f"  DECP : {d_cat}")

    # ── Write markdown report ──────────────────────────────────────────────
    report = f"""# Week 2 – Cleaning and Normalization Report

## Scope
- BOAMP sample: {n_b} notices (PdL, digital CPV, 2015-2024)
- DECP filtered: {n_d} contracts (PdL, digital CPV, 2015-2024, current version)

## Buyer normalization
Canonical key strategy: **SIRET (14-digit) when valid, normalized name otherwise**.

| Source | Raw unique names | Canonical keys | SIRET-anchored |
|--------|-----------------|----------------|----------------|
| BOAMP  | {b_buyer_before} | {b_buyer_after} | {b_siret_keys} rows ({round(100*b_siret_keys/n_b,1)}% of notices) |
| DECP   | {d_buyer_before} | {d_buyer_after} | {d_siret_keys} rows ({round(100*d_siret_keys/n_d,1)}% of contracts) |

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
| BOAMP  | {b_amt_zero} | {b_amt_tiny} | {b_amt_ceil} | {b_amt_clean_rate}% |
| DECP   | {d_amt_zero} | {d_amt_tiny} | {d_amt_ceil} | {d_amt_clean_rate}% |

**Remaining missing values** in amount_clean come from original NaN fields and are **not imputed at this stage** (Week-3 modeling will use median-by-segment imputation for covariates that need a numeric value).

## Duration cleaning
Flagging rule: `flag_duration_suspect` = 1 when `dureeMois` / `duration_months` outside [{DURATION_MIN_MONTHS}, {DURATION_MAX_MONTHS}] months.
Suspect values are set to NaN in `duration_clean` but kept raw.

| Source | Suspect flags |
|--------|---------------|
| BOAMP  | {b_dur_suspect} |
| DECP   | {d_dur_suspect} |

## Taxonomy tagging (10 categories)
CPV-prefix match first; keyword-in-objet fallback.  Full taxonomy: `taxonomy.csv`.

| Category | BOAMP | DECP |
|----------|-------|------|
"""
    all_cats = sorted(set(list(b_cat.keys()) + list(d_cat.keys())))
    for cat in all_cats:
        report += f"| {cat} | {b_cat.get(cat,0)} | {d_cat.get(cat,0)} |\n"

    report += f"""
## Known limitations
1. BOAMP SIRET coverage is only {round(100*b_siret_keys/n_b,1)}% of notices: legacy notices carry no SIRET. Name-based matching is imprecise for common institutional names (e.g. "SDIS 44").
2. Amount ceilings (≥10 M) for framework agreements cannot be distinguished automatically without human review.
3. Taxonomy tagging via CPV prefix is deterministic but will miss contracts with generic CPV codes (e.g. 72000000) not rescued by keyword fallback.
"""
    report_out = PROCESSED_DIR / "week2_cleaning_report.md"
    report_out.write_text(report)
    print(f"\nSaved report: {report_out}")


if __name__ == "__main__":
    main()
