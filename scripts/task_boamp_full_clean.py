"""BOAMP full clean — apply cleaning rules to boamp_full_flat.csv.

Same logic as task7 BOAMP section, but reads from the full download
(3 181 records) instead of the 500-record sample.

Outputs
-------
  data/processed/boamp_full_clean.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from task7_week2_cleaning import (
    apply_amount_flags,
    apply_duration_flags,
    build_taxonomy_matcher,
    canonical_buyer_key,
    clean_cpv,
)
from utils import PROCESSED_DIR


def main() -> None:
    taxonomy = pd.read_csv(PROCESSED_DIR / "taxonomy.csv", dtype=str)
    matcher = build_taxonomy_matcher(taxonomy)

    boamp = pd.read_csv(
        PROCESSED_DIR / "boamp_full_flat.csv",
        dtype={"buyer_siret": str, "cpv_principal": str},
    )

    boamp["buyer_key"] = [
        canonical_buyer_key(s, n)
        for s, n in zip(boamp["buyer_siret"], boamp["nomacheteur"])
    ]

    # CPV hierarchy: 8-digit full code → 5-digit category → 4-digit class →
    # 3-digit group → 2-digit division (https://www.code-commande-publique.com/cpv-nomenclature/).
    boamp["cpv_clean"] = boamp["cpv_principal"].map(clean_cpv)
    boamp["cpv_full8"] = boamp["cpv_clean"]
    boamp["cpv_div2"] = boamp["cpv_clean"].str[:2]
    boamp["cpv_group3"] = boamp["cpv_clean"].str[:3]
    boamp["cpv_class4"] = boamp["cpv_clean"].str[:4]
    boamp["cpv_category5"] = boamp["cpv_clean"].str[:5]
    boamp["cpv_is_missing"] = boamp["cpv_clean"].isna()
    # Generic / catch-all codes end in many zeros (e.g. 72000000) — division-level only.
    boamp["cpv_is_generic"] = boamp["cpv_clean"].fillna("").str.endswith("000000")

    amt_flags = apply_amount_flags(boamp["amount_eur"])
    boamp = pd.concat([boamp, amt_flags], axis=1)

    dur_flags = apply_duration_flags(boamp["duration_months"])
    boamp = pd.concat([
        boamp,
        dur_flags.rename(columns={
            "duration_raw": "duration_raw_boamp",
            "flag_duration_suspect": "flag_duration_suspect",
            "duration_clean": "duration_clean",
        }),
    ], axis=1)

    tags = [matcher(c, o) for c, o in zip(boamp["cpv_clean"], boamp["objet"])]
    boamp["category_id"] = [t[0] for t in tags]
    boamp["category_label"] = [t[1] for t in tags]

    out = PROCESSED_DIR / "boamp_full_clean.csv"
    boamp.to_csv(out, index=False)

    n = len(boamp)
    ao = boamp[boamp["nature"] == "APPEL_OFFRE"]
    print("=== BOAMP full clean summary ===")
    print(f"Total records     : {n}")
    print(f"APPEL_OFFRE       : {len(ao)}")
    print(f"ATTRIBUTION       : {(boamp['nature']=='ATTRIBUTION').sum()}")
    print(f"RECTIFICATIF      : {(boamp['nature']=='RECTIFICATIF').sum()}")
    print(f"buyer_key SIRET   : {boamp['buyer_key'].str.startswith('SIRET:').sum()} ({boamp['buyer_key'].str.startswith('SIRET:').mean()*100:.1f}%)")
    print(f"duration_clean    : {boamp['duration_clean'].notna().sum()}/{n} ({boamp['duration_clean'].notna().mean()*100:.1f}%)")
    print(f"amount_clean      : {boamp['amount_clean'].notna().sum()}/{n} ({boamp['amount_clean'].notna().mean()*100:.1f}%)")
    print(f"\nCategory breakdown:")
    print(boamp["category_label"].value_counts().to_string())
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
