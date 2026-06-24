"""Step 4 — Join the enriched buyer table back to the full BOAMP dataset.

Left-join on nomacheteur → buyer_name_raw.
Adds enrichment columns; original buyer_key preserved as buyer_key_original.

Output
------
  data/processed/boamp_full_clean_siren_enriched.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

BOAMP_CLEAN  = ROOT / "data" / "processed" / "boamp_full_clean.csv"
ENRICHED_TBL = ROOT / "buyer_siren_enrichment" / "outputs" / "boamp_buyer_siren_enriched.csv"
OUT_FILE     = ROOT / "data" / "processed" / "boamp_full_clean_siren_enriched.csv"

ENRICH_COLS = [
    "buyer_name_raw",
    "buyer_key_enriched",
    "enriched_siren",
    "enriched_siret",
    "enrichment_confidence",
    "enrichment_score",
    "enrichment_source",
    "enrichment_status",
]


def main() -> None:
    boamp    = pd.read_csv(BOAMP_CLEAN, dtype={"buyer_siret": str, "buyer_cp": str,
                                                "code_departement": str}, low_memory=False)
    enriched = pd.read_csv(ENRICHED_TBL, dtype={"enriched_siren": str,
                                                  "enriched_siret": str})

    n_before = len(boamp)
    print(f"BOAMP rows: {n_before:,}")
    print(f"Enriched buyers: {len(enriched):,}")

    # Rename original buyer_key before the merge
    boamp = boamp.rename(columns={"buyer_key": "buyer_key_original"})

    # Merge on buyer name
    merged = boamp.merge(
        enriched[ENRICH_COLS].rename(columns={"buyer_name_raw": "nomacheteur"}),
        on="nomacheteur",
        how="left",
    )

    n_after = len(merged)
    assert n_after == n_before, (
        f"Row count changed after join: {n_before} → {n_after}. "
        "Check for duplicate buyer_name_raw in enriched table."
    )

    # For rows where no enrichment (NaN), fill buyer_key_enriched = buyer_key_original
    missing = merged["buyer_key_enriched"].isna()
    merged.loc[missing, "buyer_key_enriched"] = merged.loc[missing, "buyer_key_original"]
    merged.loc[missing, "enrichment_status"]  = "no_match"

    merged.to_csv(OUT_FILE, index=False)

    siren_keys   = merged["buyer_key_enriched"].str.startswith("SIREN:").sum()
    name_keys    = merged["buyer_key_enriched"].str.startswith("NAME:").sum()
    siret_keys   = merged["buyer_key_enriched"].str.startswith("SIRET:").sum()
    high_rows    = (merged["enrichment_confidence"] == "HIGH").sum()

    print(f"\n=== Enriched BOAMP dataset ===")
    print(f"Rows: {n_after:,}  |  Columns: {len(merged.columns)}")
    print(f"buyer_key_enriched breakdown:")
    print(f"  SIREN:  {siren_keys:,} rows ({siren_keys/n_after*100:.1f}%)")
    print(f"  SIRET:  {siret_keys:,} rows ({siret_keys/n_after*100:.1f}%)")
    print(f"  NAME:   {name_keys:,} rows ({name_keys/n_after*100:.1f}%)")
    print(f"HIGH-confidence rows: {high_rows:,} ({high_rows/n_after*100:.1f}%)")
    print(f"Saved → {OUT_FILE}")


if __name__ == "__main__":
    main()
