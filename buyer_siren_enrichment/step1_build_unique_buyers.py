"""Step 1 — Build the unique BOAMP buyer table.

One row per unique nomacheteur. Aggregates counts, location signals, and
existing SIRET metadata so that step2 can query the API once per buyer
instead of once per notice.

Output
------
  buyer_siren_enrichment/outputs/boamp_unique_buyers_for_enrichment.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd
from task7_week2_cleaning import normalize_name

BOAMP_CLEAN = ROOT / "data" / "processed" / "boamp_full_clean.csv"
OUT_DIR     = ROOT / "buyer_siren_enrichment" / "outputs"
OUT_FILE    = OUT_DIR / "boamp_unique_buyers_for_enrichment.csv"


def _first_dept(raw) -> str | None:
    """Return the first department code from pipe-separated values."""
    if pd.isna(raw):
        return None
    return str(raw).split("|")[0].strip() or None


def _mode_or_first(series: pd.Series):
    """Most common non-null value, or first non-null if all unique."""
    s = series.dropna()
    if s.empty:
        return None
    return s.mode().iloc[0] if not s.mode().empty else s.iloc[0]


def build(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, grp in df.groupby("nomacheteur", sort=False):
        dept_raw = _mode_or_first(grp["code_departement"])
        dept_code = _first_dept(dept_raw) if dept_raw else None

        siret_vals = (
            grp["buyer_siret"]
            .dropna()
            .astype(str)
            .str.strip()
            .pipe(lambda s: s[s.str.match(r"^\d{9,14}$")])
            .unique()
            .tolist()
        )

        rows.append({
            "buyer_name_raw":            name,
            "buyer_name_clean":          normalize_name(name),
            "buyer_key":                 _mode_or_first(grp["buyer_key"]),
            "dept_code":                 dept_code,
            "city":                      _mode_or_first(grp["buyer_ville"]),
            "postal_code":               _mode_or_first(grp["buyer_cp"]),
            "n_notices":                 len(grp),
            "n_appel_offre":             (grp["nature"] == "APPEL_OFFRE").sum(),
            "has_existing_boamp_siret":  len(siret_vals) > 0,
            "existing_siret_values":     "|".join(siret_vals) if siret_vals else None,
        })

    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(BOAMP_CLEAN, dtype={"buyer_siret": str, "buyer_cp": str,
                                          "code_departement": str}, low_memory=False)
    print(f"Loaded {len(df):,} BOAMP rows, {df['nomacheteur'].nunique():,} unique nomacheteur values")

    buyers = build(df)
    buyers.to_csv(OUT_FILE, index=False)

    name_keys = buyers["buyer_key"].str.startswith("NAME:").sum()
    siret_keys = buyers["buyer_key"].str.startswith("SIRET:").sum()
    has_siret  = buyers["has_existing_boamp_siret"].sum()
    print(f"Unique buyers: {len(buyers):,}")
    print(f"  NAME: keyed   : {name_keys:,} ({name_keys/len(buyers)*100:.1f}%)")
    print(f"  SIRET: keyed  : {siret_keys:,} ({siret_keys/len(buyers)*100:.1f}%)")
    print(f"  Have BOAMP SIRET: {has_siret:,}")
    print(f"Saved → {OUT_FILE}")


if __name__ == "__main__":
    main()
