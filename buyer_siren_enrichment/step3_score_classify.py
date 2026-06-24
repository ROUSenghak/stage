"""Step 3 — Score, classify, and build the enriched buyer table.

Reads the full candidates table (one row per candidate) and collapses to
one row per buyer with a confidence classification and the new buyer_key_enriched.

Confidence rules
----------------
  HIGH   : best_score >= 85
           OR (best_score >= 75 AND n_candidates == 1)
           OR (best_score >= 75 AND margin >= 10)
  MEDIUM : best_score >= 70 (and not HIGH)
  LOW    : best_score >= 55 (and not MEDIUM)
  NO_MATCH: best_score < 55 OR no candidates returned

buyer_key_enriched
------------------
  HIGH + valid SIREN  →  "SIREN:" + enriched_siren
  otherwise           →  original buyer_key (NEVER changed for MEDIUM/LOW/NO_MATCH)

Output
------
  buyer_siren_enrichment/outputs/boamp_buyer_siren_enriched.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

ENRICH_DIR  = ROOT / "buyer_siren_enrichment"
CANDS_CSV   = ENRICH_DIR / "outputs" / "boamp_buyer_siren_candidates.csv"
BUYERS_CSV  = ENRICH_DIR / "outputs" / "boamp_unique_buyers_for_enrichment.csv"
OUT_FILE    = ENRICH_DIR / "outputs" / "boamp_buyer_siren_enriched.csv"

HIGH_SCORE        = 85.0
HIGH_SCORE_LOWER  = 75.0
MEDIUM_SCORE      = 70.0
LOW_SCORE         = 55.0
HIGH_MARGIN       = 10.0


def _classify(best_score: float, second_score: float | None,
              n_candidates: int) -> str:
    margin = (best_score - second_score) if second_score is not None else None

    if best_score >= HIGH_SCORE:
        return "HIGH"
    if best_score >= HIGH_SCORE_LOWER:
        if n_candidates == 1:
            return "HIGH"
        if margin is not None and margin >= HIGH_MARGIN:
            return "HIGH"
    if best_score >= MEDIUM_SCORE:
        return "MEDIUM"
    if best_score >= LOW_SCORE:
        return "LOW"
    return "NO_MATCH"


def _diagnostic(confidence: str, best_score: float, second_score: float | None,
                n_candidates: int) -> str:
    if n_candidates == 0:
        return "no API candidates returned"
    margin = (best_score - second_score) if second_score is not None else None
    if confidence == "HIGH":
        return f"score={best_score:.1f}, n_cands={n_candidates}, margin={'%.1f' % margin if margin is not None else 'N/A'}"
    if confidence == "MEDIUM":
        return f"score={best_score:.1f} (below HIGH threshold or margin too small)"
    if confidence == "LOW":
        return f"score={best_score:.1f} (below MEDIUM threshold)"
    return f"score={best_score:.1f} (below LOW threshold)"


def classify(cands: pd.DataFrame, buyers: pd.DataFrame) -> pd.DataFrame:
    rows = []

    buyers_idx = buyers.set_index("buyer_name_raw")

    for buyer_name, grp in cands.groupby("buyer_name_raw", sort=False):
        buyer_row   = buyers_idx.loc[buyer_name] if buyer_name in buyers_idx.index else {}
        buyer_key   = grp["buyer_key"].iloc[0]
        name_clean  = grp["buyer_name_clean"].iloc[0]
        dept_code   = grp["dept_code"].iloc[0] if not grp["dept_code"].isna().all() else None

        # Split candidates from no-candidate sentinel row
        has_cands = grp["candidate_rank"].notna()
        real_cands = grp[has_cands].sort_values("candidate_rank")
        n_candidates = len(real_cands)

        if n_candidates == 0:
            best_score, second_score = 0.0, None
            best_siren = best_siret = best_name = None
            confidence = "NO_MATCH"
            enrichment_status = "no_match"
        else:
            best       = real_cands.iloc[0]
            best_score = float(best["enrichment_score"])
            second_score = (
                float(real_cands.iloc[1]["enrichment_score"])
                if n_candidates >= 2 else None
            )
            best_siren = best["candidate_siren"] or None
            best_siret = best["candidate_siret"] or None
            best_name  = best["candidate_name"] or None

            confidence = _classify(best_score, second_score, n_candidates)
            enrichment_status = "matched" if confidence != "NO_MATCH" else "no_match"

        margin = (best_score - second_score) if second_score is not None else None

        # buyer_key_enriched: SIREN: only for HIGH + valid SIREN
        if confidence == "HIGH" and best_siren:
            buyer_key_enriched = f"SIREN:{best_siren}"
            enrichment_status  = "matched"
        else:
            buyer_key_enriched = buyer_key  # unchanged
            if confidence == "HIGH" and not best_siren:
                enrichment_status = "no_match"  # no SIREN despite high score

        # buyers already keyed as SIRET: from raw BOAMP data
        if isinstance(buyer_key, str) and buyer_key.startswith("SIRET:"):
            enrichment_status = "skipped_already_siret"

        rows.append({
            "buyer_name_raw":        buyer_name,
            "buyer_name_clean":      name_clean,
            "buyer_key":             buyer_key,
            "buyer_key_enriched":    buyer_key_enriched,
            "enriched_siren":        best_siren if confidence == "HIGH" else None,
            "enriched_siret":        best_siret if confidence == "HIGH" else None,
            "enriched_name":         best_name  if confidence == "HIGH" else None,
            "enrichment_score":      round(best_score, 1) if n_candidates > 0 else None,
            "enrichment_confidence": confidence,
            "enrichment_source":     "api_recherche_entreprises",
            "enrichment_status":     enrichment_status,
            "diagnostic":            _diagnostic(confidence, best_score, second_score, n_candidates),
            "n_candidates":          n_candidates,
            "margin":                round(margin, 1) if margin is not None else None,
        })

    return pd.DataFrame(rows)


def main() -> None:
    cands  = pd.read_csv(CANDS_CSV, dtype={"dept_code": str, "candidate_siren": str,
                                            "candidate_siret": str})
    buyers = pd.read_csv(BUYERS_CSV, dtype={"dept_code": str})

    # Ensure enrichment_score is numeric
    cands["enrichment_score"] = pd.to_numeric(cands["enrichment_score"], errors="coerce").fillna(0.0)

    print(f"Candidates: {len(cands):,} rows, {cands['buyer_name_raw'].nunique():,} buyers")

    enriched = classify(cands, buyers)
    enriched.to_csv(OUT_FILE, index=False)

    conf_counts = enriched["enrichment_confidence"].value_counts()
    total = len(enriched)
    upgraded = (enriched["buyer_key_enriched"].str.startswith("SIREN:")).sum()

    print(f"\n=== Confidence distribution ({total} unique buyers) ===")
    for conf in ["HIGH", "MEDIUM", "LOW", "NO_MATCH"]:
        n = conf_counts.get(conf, 0)
        print(f"  {conf:8s}: {n:4d}  ({n/total*100:.1f}%)")
    print(f"\nKeys upgraded to SIREN: : {upgraded} ({upgraded/total*100:.1f}%)")
    print(f"Saved → {OUT_FILE}")


if __name__ == "__main__":
    main()
