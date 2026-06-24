"""Step 5 — Enrichment quality report.

Reads the enriched buyer table and the enriched BOAMP dataset to produce
three diagnostic CSV files for human review.

Outputs
-------
  buyer_siren_enrichment/outputs/enrichment_quality_summary.csv
  buyer_siren_enrichment/outputs/top_unmatched_buyers.csv
  buyer_siren_enrichment/outputs/ambiguous_buyer_matches_for_review.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

ENRICH_DIR   = ROOT / "buyer_siren_enrichment"
ENRICHED_TBL = ENRICH_DIR / "outputs" / "boamp_buyer_siren_enriched.csv"
BOAMP_ENR    = ROOT / "data" / "processed" / "boamp_full_clean_siren_enriched.csv"
OUT_SUMMARY  = ENRICH_DIR / "outputs" / "enrichment_quality_summary.csv"
OUT_UNMATCH  = ENRICH_DIR / "outputs" / "top_unmatched_buyers.csv"
OUT_AMBIG    = ENRICH_DIR / "outputs" / "ambiguous_buyer_matches_for_review.csv"
CANDS_CSV    = ENRICH_DIR / "outputs" / "boamp_buyer_siren_candidates.csv"


def main() -> None:
    buyers = pd.read_csv(ENRICHED_TBL, dtype={"enriched_siren": str, "enriched_siret": str})
    boamp  = pd.read_csv(BOAMP_ENR, low_memory=False)
    cands  = pd.read_csv(CANDS_CSV,  dtype={"dept_code": str})

    total_buyers = len(buyers)
    conf = buyers["enrichment_confidence"].value_counts()

    n_high     = conf.get("HIGH",     0)
    n_medium   = conf.get("MEDIUM",   0)
    n_low      = conf.get("LOW",      0)
    n_no_match = conf.get("NO_MATCH", 0)

    # Notices covered by HIGH-confidence SIREN
    high_rows  = boamp[boamp["enrichment_confidence"] == "HIGH"]
    ao_rows    = boamp[boamp["nature"] == "APPEL_OFFRE"]
    ao_high    = ao_rows[ao_rows["enrichment_confidence"] == "HIGH"]

    # How many original NAME: keys were upgraded to SIREN:
    n_upgraded = (
        buyers["buyer_key_enriched"].str.startswith("SIREN:")
    ).sum()

    # Deduplication merges: SIRENs that map to >1 original buyer_key
    high_buyers = buyers[buyers["enrichment_confidence"] == "HIGH"].copy()
    if "enriched_siren" in high_buyers.columns and high_buyers["enriched_siren"].notna().any():
        siren_groups = (
            high_buyers.dropna(subset=["enriched_siren"])
            .groupby("enriched_siren")["buyer_key"]
            .nunique()
        )
        n_merges = int((siren_groups > 1).sum())
    else:
        n_merges = 0

    summary = pd.DataFrame([{
        "n_unique_buyers":             total_buyers,
        "n_high":                      n_high,
        "n_medium":                    n_medium,
        "n_low":                       n_low,
        "n_no_match":                  n_no_match,
        "pct_high":                    round(n_high / total_buyers * 100, 1),
        "pct_medium":                  round(n_medium / total_buyers * 100, 1),
        "pct_low":                     round(n_low / total_buyers * 100, 1),
        "pct_no_match":                round(n_no_match / total_buyers * 100, 1),
        "pct_notices_high_conf":       round(len(high_rows) / len(boamp) * 100, 1),
        "pct_appel_offre_high_conf":   round(len(ao_high) / len(ao_rows) * 100, 1) if len(ao_rows) > 0 else 0,
        "n_keys_upgraded_to_siren":    n_upgraded,
        "n_siren_deduplication_merges": n_merges,
        "n_total_notices":             len(boamp),
        "n_high_conf_notices":         len(high_rows),
        "n_appel_offre_total":         len(ao_rows),
        "n_appel_offre_high_conf":     len(ao_high),
    }])
    summary.to_csv(OUT_SUMMARY, index=False)

    # ── Top unmatched buyers ────────────────────────────────────────────────
    no_match = buyers[buyers["enrichment_confidence"] == "NO_MATCH"].copy()

    # Pull back n_notices and n_appel_offre from buyers table if available
    buyers_full = pd.read_csv(
        ENRICH_DIR / "outputs" / "boamp_unique_buyers_for_enrichment.csv",
        dtype={"dept_code": str},
    )
    no_match = no_match.merge(
        buyers_full[["buyer_name_raw", "n_notices", "n_appel_offre", "dept_code"]],
        on="buyer_name_raw", how="left", suffixes=("", "_b"),
    )
    # Pull query_used from candidates table
    first_cand = (
        cands[cands["candidate_rank"].isna() | (cands["candidate_rank"] == 1)]
        .drop_duplicates("buyer_name_raw")[["buyer_name_raw", "query_used"]]
    )
    no_match = no_match.merge(first_cand, on="buyer_name_raw", how="left")

    top_unmatched = (
        no_match[["buyer_name_raw", "buyer_key", "n_notices", "n_appel_offre",
                   "dept_code", "query_used", "diagnostic"]]
        .sort_values("n_notices", ascending=False)
        .head(30)
    )
    top_unmatched.to_csv(OUT_UNMATCH, index=False)

    # ── Ambiguous matches (MEDIUM + LOW) ────────────────────────────────────
    ambig = buyers[buyers["enrichment_confidence"].isin(["MEDIUM", "LOW"])].copy()
    ambig = ambig.merge(
        buyers_full[["buyer_name_raw", "n_notices", "n_appel_offre", "dept_code"]],
        on="buyer_name_raw", how="left", suffixes=("", "_b"),
    )
    ambig_out = ambig[[
        "buyer_name_raw", "enriched_name", "enriched_siren",
        "enrichment_score", "enrichment_confidence",
        "n_notices", "dept_code", "diagnostic", "n_candidates", "margin",
    ]].sort_values(["enrichment_confidence", "n_notices"], ascending=[True, False])
    ambig_out.to_csv(OUT_AMBIG, index=False)

    print("=== Enrichment Quality Summary ===")
    print(f"Unique buyers  : {total_buyers}")
    print(f"  HIGH         : {n_high:4d}  ({n_high/total_buyers*100:.1f}%)")
    print(f"  MEDIUM       : {n_medium:4d}  ({n_medium/total_buyers*100:.1f}%)")
    print(f"  LOW          : {n_low:4d}  ({n_low/total_buyers*100:.1f}%)")
    print(f"  NO_MATCH     : {n_no_match:4d}  ({n_no_match/total_buyers*100:.1f}%)")
    print(f"Notices HIGH-conf: {len(high_rows)}/{len(boamp)} ({len(high_rows)/len(boamp)*100:.1f}%)")
    print(f"AO HIGH-conf    : {len(ao_high)}/{len(ao_rows)} ({len(ao_high)/len(ao_rows)*100:.1f}%)")
    print(f"Keys upgraded   : {n_upgraded}")
    print(f"SIREN merges    : {n_merges}")
    print(f"\nSaved:\n  {OUT_SUMMARY}\n  {OUT_UNMATCH}\n  {OUT_AMBIG}")


if __name__ == "__main__":
    main()
