"""Step 7 — Baseline vs. SIREN-enriched comparison.

Compares the Jaccard-based baseline (boamp_full_survival.csv) with the
SIREN-enriched version (boamp_full_survival_enriched.csv) across key
survival and linking metrics.

Also annotates the phase2 survival dataset (boamp_phase2_survival.csv)
with SIREN metadata — without re-running the notebook.

Outputs
-------
  buyer_siren_enrichment/outputs/baseline_vs_siren_enriched_linking_comparison.csv
  buyer_siren_enrichment/outputs/baseline_vs_siren_enriched_survival_comparison.csv
  data/processed/boamp_phase2_survival_siren_enriched.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

ENRICH_DIR   = ROOT / "buyer_siren_enrichment"
BASELINE_CSV = ROOT / "data" / "processed" / "boamp_full_survival.csv"
ENRICHED_CSV = ROOT / "boamp_renewal_linking_siren_enriched" / "outputs" / "boamp_full_survival_enriched.csv"
PHASE2_CSV   = ROOT / "data" / "processed" / "boamp_phase2_survival.csv"
BUYERS_TBL   = ENRICH_DIR / "outputs" / "boamp_buyer_siren_enriched.csv"
QUALITY_SUM  = ENRICH_DIR / "outputs" / "enrichment_quality_summary.csv"

OUT_LINK_CMP   = ENRICH_DIR / "outputs" / "baseline_vs_siren_enriched_linking_comparison.csv"
OUT_SURV_CMP   = ENRICH_DIR / "outputs" / "baseline_vs_siren_enriched_survival_comparison.csv"
OUT_PHASE2_ENR = ROOT / "data" / "processed" / "boamp_phase2_survival_siren_enriched.csv"


def _summary_row(df: pd.DataFrame, label: str) -> dict:
    n         = len(df)
    n_events  = int(df["event"].sum())
    n_censored = n - n_events
    event_rate = round(100 * n_events / n, 1) if n > 0 else 0.0

    # buyer_key column name differs between baseline and enriched
    bk_col = "buyer_key_enriched" if "buyer_key_enriched" in df.columns else "buyer_key"
    cpv_col = "cpv_div2"
    n_groups = df.groupby([bk_col, cpv_col], dropna=False).ngroups

    return {
        "dataset":           label,
        "n_eligible":        n,
        "n_events":          n_events,
        "event_rate_pct":    event_rate,
        "n_censored":        n_censored,
        "n_groups":          n_groups,
        "median_obs_months": round(df["observed_duration_months"].median(), 1),
        "median_event_months": (
            round(df.loc[df["event"] == 1, "observed_duration_months"].median(), 1)
            if n_events > 0 else None
        ),
    }


def _event_rate_by_col(df: pd.DataFrame, col: str, label: str) -> pd.DataFrame:
    bk_col = "buyer_key_enriched" if "buyer_key_enriched" in df.columns else "buyer_key"
    grp = (
        df.groupby(col, as_index=False)
        .agg(n=("contract_id", "count"), events=("event", "sum"))
    )
    grp["event_rate_pct"] = (100 * grp["events"] / grp["n"]).round(1)
    grp["dataset"] = label
    return grp


def main() -> None:
    ENRICH_DIR.mkdir(parents=True, exist_ok=True)

    baseline = pd.read_csv(BASELINE_CSV)
    enriched = pd.read_csv(ENRICHED_CSV)
    buyers   = pd.read_csv(BUYERS_TBL, dtype={"enriched_siren": str, "enriched_siret": str})

    print(f"Baseline  : {len(baseline):,} rows, event_rate={baseline['event'].mean()*100:.1f}%")
    print(f"Enriched  : {len(enriched):,} rows, event_rate={enriched['event'].mean()*100:.1f}%")

    # ── Overall linking comparison ─────────────────────────────────────────
    quality_sum = pd.read_csv(QUALITY_SUM) if QUALITY_SUM.exists() else pd.DataFrame()
    n_upgraded = int(quality_sum["n_keys_upgraded_to_siren"].iloc[0]) if not quality_sum.empty else None
    n_merges   = int(quality_sum["n_siren_deduplication_merges"].iloc[0]) if not quality_sum.empty else None

    base_row = _summary_row(baseline, "baseline_jaccard")
    enr_row  = _summary_row(enriched, "siren_enriched_jaccard")
    base_row.update({"n_keys_upgraded_to_siren": None, "n_siren_deduplication_merges": None})
    enr_row.update({"n_keys_upgraded_to_siren": n_upgraded, "n_siren_deduplication_merges": n_merges})

    # Add delta row
    delta_row = {
        "dataset":           "delta (enriched - baseline)",
        "n_eligible":        enr_row["n_eligible"] - base_row["n_eligible"],
        "n_events":          enr_row["n_events"]   - base_row["n_events"],
        "event_rate_pct":    round(enr_row["event_rate_pct"] - base_row["event_rate_pct"], 2),
        "n_censored":        enr_row["n_censored"] - base_row["n_censored"],
        "n_groups":          enr_row["n_groups"]   - base_row["n_groups"],
        "median_obs_months": None,
        "median_event_months": None,
        "n_keys_upgraded_to_siren": n_upgraded,
        "n_siren_deduplication_merges": n_merges,
    }

    link_cmp = pd.DataFrame([base_row, enr_row, delta_row])
    link_cmp.to_csv(OUT_LINK_CMP, index=False)
    print(f"\nSaved linking comparison → {OUT_LINK_CMP}")

    # ── By-category comparison ─────────────────────────────────────────────
    base_cat = _event_rate_by_col(baseline, "category_label", "baseline")
    enr_cat  = _event_rate_by_col(enriched, "category_label", "siren_enriched")
    cat_cmp  = pd.concat([base_cat, enr_cat], ignore_index=True)

    # ── By-year comparison ─────────────────────────────────────────────────
    for df in [baseline, enriched]:
        df["year"] = pd.to_datetime(df["start_date"], errors="coerce").dt.year

    base_yr = _event_rate_by_col(baseline, "year", "baseline")
    enr_yr  = _event_rate_by_col(enriched,  "year", "siren_enriched")
    yr_cmp  = pd.concat([base_yr, enr_yr], ignore_index=True)

    # ── Survival comparison ────────────────────────────────────────────────
    surv_rows = []

    # Try KM via lifelines
    try:
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test

        kmf_base = KaplanMeierFitter()
        kmf_enr  = KaplanMeierFitter()
        kmf_base.fit(baseline["observed_duration_months"], baseline["event"], label="baseline")
        kmf_enr.fit(enriched["observed_duration_months"],  enriched["event"],  label="enriched")

        lr = logrank_test(
            baseline["observed_duration_months"], enriched["observed_duration_months"],
            baseline["event"], enriched["event"],
        )

        for label, kmf, df in [("baseline", kmf_base, baseline), ("siren_enriched", kmf_enr, enriched)]:
            surv_rows.append({
                "dataset":          label,
                "n_eligible":       len(df),
                "event_rate_pct":   round(df["event"].mean() * 100, 1),
                "km_median_months": kmf.median_survival_time_,
                "logrank_p_value":  round(lr.p_value, 4),
                "km_method":        "KaplanMeierFitter (lifelines)",
            })
        print("KM estimation completed (lifelines available).")

    except ImportError:
        print("lifelines not installed — outputting descriptive stats only.")
        for label, df in [("baseline", baseline), ("siren_enriched", enriched)]:
            ev = df[df["event"] == 1]["observed_duration_months"]
            surv_rows.append({
                "dataset":          label,
                "n_eligible":       len(df),
                "event_rate_pct":   round(df["event"].mean() * 100, 1),
                "km_median_months": None,
                "logrank_p_value":  None,
                "km_method":        "descriptive_only (lifelines not installed)",
                "mean_event_months": round(ev.mean(), 1) if len(ev) > 0 else None,
                "median_event_months": round(ev.median(), 1) if len(ev) > 0 else None,
            })

    surv_cmp = pd.DataFrame(surv_rows)
    cat_extra = cat_cmp.rename(
        columns={"category_label": "breakdown_value", "n": "n_in_group",
                 "event_rate_pct": "group_event_rate_pct"}
    ).assign(n_eligible=float("nan"), event_rate_pct=float("nan"),
             km_median_months=float("nan"), logrank_p_value=float("nan"),
             km_method="by_category")
    for col in surv_cmp.columns:
        if col not in cat_extra.columns:
            cat_extra[col] = float("nan") if surv_cmp[col].dtype.kind in "fiu" else None
    surv_cmp = pd.concat([surv_cmp, cat_extra[surv_cmp.columns]], ignore_index=True)
    surv_cmp.to_csv(OUT_SURV_CMP, index=False)
    print(f"Saved survival comparison → {OUT_SURV_CMP}")

    # ── Phase2 annotation ──────────────────────────────────────────────────
    # After the phase-2 notebook was re-run with buyer_key_enriched as the
    # active grouping key, phase2's buyer_key column now holds the *enriched*
    # key (SIREN:... for 660 rows, NAME:... for 440 rows). The enrichment
    # lookup table (boamp_buyer_siren_enriched.csv) is keyed by the *original*
    # buyer_key (NAME:/SIRET:) and has buyer_key_enriched = SIREN: for HIGH
    # confidence matches. A direct join on buyer_key therefore fails for the
    # SIREN: rows. We use a two-step join:
    #   1. NAME:/SIRET: rows in phase2 → join on buyer_key (original key match)
    #   2. SIREN: rows in phase2 → join on buyer_key_enriched from the lookup
    #      (phase2.buyer_key == lookup.buyer_key_enriched)
    phase2 = pd.read_csv(PHASE2_CSV)
    n_phase2 = len(phase2)

    enrich_cols = ["buyer_key", "buyer_key_enriched", "enriched_siren",
                   "enrichment_confidence", "enrichment_score"]
    meta_cols   = ["buyer_key_enriched", "enriched_siren",
                   "enrichment_confidence", "enrichment_score"]
    conf_order  = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NO_MATCH": 3}

    # Lookup 1: original buyer_key → enrichment metadata (NAME:/SIRET: rows)
    lookup_by_orig = (
        buyers[enrich_cols]
        .assign(_r=buyers["enrichment_confidence"].map(conf_order).fillna(9))
        .sort_values(["buyer_key", "_r"])
        .drop_duplicates(subset=["buyer_key"], keep="first")
        .drop(columns=["_r"])
    )

    # Lookup 2: enriched buyer_key → enrichment metadata (SIREN: rows in phase2)
    # Re-key the lookup by buyer_key_enriched so we can match phase2.buyer_key
    # = "SIREN:..." against lookup.buyer_key_enriched = "SIREN:...".
    lookup_by_enr = (
        buyers[enrich_cols]
        .assign(_r=buyers["enrichment_confidence"].map(conf_order).fillna(9))
        .sort_values(["buyer_key_enriched", "_r"])
        .drop_duplicates(subset=["buyer_key_enriched"], keep="first")
        .drop(columns=["_r", "buyer_key"])             # drop original key
        .rename(columns={"buyer_key_enriched": "buyer_key"})   # rename for merge
    )

    # Split phase2 by buyer_key prefix, preserving original integer index
    phase2 = phase2.reset_index(drop=True)
    is_siren = phase2["buyer_key"].str.startswith("SIREN:")
    p2_siren = phase2[is_siren].copy()
    p2_other = phase2[~is_siren].copy()

    # Join NAME:/SIRET: rows on original key
    p2_other_enr = p2_other.merge(lookup_by_orig, on="buyer_key", how="left")
    p2_other_enr.index = p2_other.index

    # Join SIREN: rows on enriched key
    p2_siren_enr = p2_siren.merge(lookup_by_enr, on="buyer_key", how="left")
    p2_siren_enr.index = p2_siren.index

    # Recombine preserving original row order via index
    phase2_enr = (
        pd.concat([p2_other_enr, p2_siren_enr])
        .sort_index()
        .reset_index(drop=True)
    )

    # Fill any remaining missing buyer_key_enriched with original buyer_key
    missing = phase2_enr["buyer_key_enriched"].isna()
    phase2_enr.loc[missing, "buyer_key_enriched"] = phase2_enr.loc[missing, "buyer_key"]

    assert len(phase2_enr) == n_phase2, "Row count changed after phase2 annotation join"

    phase2_enr.to_csv(OUT_PHASE2_ENR, index=False)
    siren_matched_p2 = (phase2_enr["enrichment_confidence"] == "HIGH").sum()
    print(f"\nPhase2 annotation: {n_phase2} rows, {siren_matched_p2} with HIGH-conf SIREN")
    print(f"Saved → {OUT_PHASE2_ENR}")

    # ── Console summary ────────────────────────────────────────────────────
    print("\n=== Baseline vs SIREN-enriched (Jaccard pipeline) ===")
    print(f"{'Metric':<30} {'Baseline':>12} {'Enriched':>12} {'Delta':>10}")
    print("-" * 66)
    for field in ["n_eligible", "n_events", "event_rate_pct", "n_groups"]:
        bv = base_row[field]
        ev = enr_row[field]
        dv = delta_row[field]
        print(f"  {field:<28} {bv:>12} {ev:>12} {dv:>+10}")


if __name__ == "__main__":
    main()
