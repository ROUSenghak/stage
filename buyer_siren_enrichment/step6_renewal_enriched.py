"""Step 6 — Renewal linking with enriched buyer key.

Identical logic to scripts/task_boamp_full_survival.py (Jaccard-based),
with two differences:
  1. Reads boamp_full_clean_siren_enriched.csv
  2. Groups by buyer_key_enriched instead of buyer_key

This gives a controlled, methodology-constant comparison: the only variable
changed is the buyer grouping key, isolating the effect of SIREN enrichment.

Note: The phase2 pipeline uses Sentence-Transformers in a Jupyter notebook
and cannot be scripted without papermill. That pipeline's baseline is preserved
untouched; step7 will annotate it with SIREN metadata rather than re-running it.

Outputs
-------
  boamp_renewal_linking_siren_enriched/outputs/boamp_full_survival_enriched.csv
  boamp_renewal_linking_siren_enriched/outputs/boamp_linking_stats_enriched.csv
  boamp_renewal_linking_siren_enriched/outputs/boamp_bias_report_enriched.csv
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

BOAMP_ENR   = ROOT / "data" / "processed" / "boamp_full_clean_siren_enriched.csv"
OUT_DIR     = ROOT / "boamp_renewal_linking_siren_enriched" / "outputs"

STUDY_END        = pd.Timestamp("2024-12-31")
WINDOW_MONTHS    = 12.0
MIN_TEXT_SIM     = 0.20
DEFAULT_DURATION = 48.0
MIN_DURATION     = 1.0
MAX_DURATION     = 120.0


# ── Helpers (identical to task_boamp_full_survival.py) ────────────────────────

def _normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text) -> set[str]:
    return {t for t in _normalize(text).split() if len(t) >= 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _month_diff(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return (end - start).days / 30.44


def _clamp(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return DEFAULT_DURATION
    if math.isnan(v):
        return DEFAULT_DURATION
    return max(MIN_DURATION, min(MAX_DURATION, v))


def build_award_index(boamp: pd.DataFrame) -> dict[str, pd.Timestamp]:
    attr = boamp[
        (boamp["nature"] == "ATTRIBUTION")
        & boamp["annonce_lie"].notna()
        & boamp["date_attribution"].notna()
    ]
    index: dict[str, pd.Timestamp] = {}
    for _, row in attr.iterrows():
        ref = str(row["annonce_lie"]).strip()
        try:
            index[ref] = pd.Timestamp(str(row["date_attribution"]))
        except Exception:
            pass
    return index


# ── Renewal linker (grouping on buyer_key_enriched) ───────────────────────────

def link_renewals(boamp: pd.DataFrame) -> pd.DataFrame:
    award_idx = build_award_index(boamp)

    ao = boamp[boamp["nature"] == "APPEL_OFFRE"].copy()
    ao["pub_date"] = pd.to_datetime(ao["dateparution"], errors="coerce")
    ao = ao[ao["pub_date"].notna() & (ao["pub_date"] <= STUDY_END)].copy()

    ao["start_date"] = ao.apply(
        lambda r: award_idx.get(str(r["idweb"]).strip(), r["pub_date"]),
        axis=1,
    )
    ao["_tokens"] = ao["objet"].map(_tokens)
    ao["_exp"]    = ao["duration_clean"].map(_clamp)

    rows = []
    # KEY CHANGE: group by buyer_key_enriched instead of buyer_key
    groups = ao.groupby(["buyer_key_enriched", "cpv_div2"], dropna=False, sort=False)

    for (buyer, cpv), grp in groups:
        grp = grp.sort_values("start_date")

        for _, src in grp.iterrows():
            start = src["start_date"]
            exp   = src["_exp"]
            low   = max(MIN_DURATION, exp - WINDOW_MONTHS)
            high  = exp + WINDOW_MONTHS

            pool = grp[grp["start_date"] > start].copy()
            if not pool.empty:
                pool["gap"] = pool["start_date"].map(lambda d: _month_diff(start, d))
                pool = pool[(pool["gap"] >= low) & (pool["gap"] <= high)]

            if not pool.empty:
                src_tok = src["_tokens"]
                pool["sim"] = pool["_tokens"].map(lambda t: _jaccard(src_tok, t))
                pool = pool[pool["sim"] >= MIN_TEXT_SIM]

            if pool.empty:
                rows.append({
                    "contract_id":              f"BOAMP:{src['idweb']}",
                    "source":                   "BOAMP",
                    "buyer_key_original":       src.get("buyer_key_original"),
                    "buyer_key_enriched":       buyer,
                    "enrichment_confidence":    src.get("enrichment_confidence"),
                    "cpv_div2":                 cpv,
                    "category_id":              src.get("category_id"),
                    "category_label":           src.get("category_label"),
                    "start_date":               start.date().isoformat(),
                    "declared_duration_months": exp,
                    "event":                    0,
                    "observed_duration_months": round(_month_diff(start, STUDY_END), 2),
                    "amount_clean":             pd.to_numeric(src.get("amount_clean"), errors="coerce"),
                    "link_method":              "none",
                    "renewal_contract_id":      None,
                    "text_similarity":          None,
                })
            else:
                pool["time_fit"] = (
                    1.0 - (pool["gap"] - exp).abs() / WINDOW_MONTHS
                ).clip(0.0, 1.0)
                pool["score"] = 0.7 * pool["sim"] + 0.3 * pool["time_fit"]
                best = pool.sort_values("score", ascending=False).iloc[0]
                rows.append({
                    "contract_id":              f"BOAMP:{src['idweb']}",
                    "source":                   "BOAMP",
                    "buyer_key_original":       src.get("buyer_key_original"),
                    "buyer_key_enriched":       buyer,
                    "enrichment_confidence":    src.get("enrichment_confidence"),
                    "cpv_div2":                 cpv,
                    "category_id":              src.get("category_id"),
                    "category_label":           src.get("category_label"),
                    "start_date":               start.date().isoformat(),
                    "declared_duration_months": exp,
                    "event":                    1,
                    "observed_duration_months": round(float(best["gap"]), 2),
                    "amount_clean":             pd.to_numeric(src.get("amount_clean"), errors="coerce"),
                    "link_method":              "boamp_jaccard",
                    "renewal_contract_id":      f"BOAMP:{best['idweb']}",
                    "text_similarity":          round(float(best["sim"]), 3),
                })

    df = pd.DataFrame(rows)
    return df[df["observed_duration_months"] > 0].copy()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    boamp = pd.read_csv(BOAMP_ENR, dtype=str, low_memory=False)
    print(f"Loaded {len(boamp):,} rows from boamp_full_clean_siren_enriched.csv")
    print(f"  APPEL_OFFRE: {(boamp['nature']=='APPEL_OFFRE').sum():,}")
    print("Running enriched renewal linker …")

    survival = link_renewals(boamp)

    out_csv = OUT_DIR / "boamp_full_survival_enriched.csv"
    survival.to_csv(out_csv, index=False)

    n         = len(survival)
    n_events  = int(survival["event"].sum())
    event_rate = round(100 * n_events / n, 1) if n else 0.0
    n_groups  = survival.groupby(["buyer_key_enriched", "cpv_div2"]).ngroups

    print(f"\n=== Enriched survival summary ===")
    print(f"Survival units  : {n:,}")
    print(f"Events (linked) : {n_events:,}  ({event_rate}%)")
    print(f"Censored        : {n - n_events:,}")
    print(f"Groups (key×cpv): {n_groups:,}")

    by_cat = (
        survival.groupby("category_label", as_index=False)
        .agg(n=("contract_id", "count"), events=("event", "sum"))
    )
    by_cat["event_rate_%"] = (100 * by_cat["events"] / by_cat["n"]).round(1)
    print("\nBy category:")
    print(by_cat.sort_values("n", ascending=False).to_string(index=False))

    # ── Linking stats ─────────────────────────────────────────────────────────
    stats = pd.DataFrame([{
        "dataset":            "enriched",
        "n_eligible":         n,
        "n_events":           n_events,
        "event_rate_pct":     event_rate,
        "n_censored":         n - n_events,
        "n_groups":           n_groups,
        "median_obs_months":  round(survival["observed_duration_months"].median(), 1),
    }])
    stats.to_csv(OUT_DIR / "boamp_linking_stats_enriched.csv", index=False)

    # ── Bias/failure report by category ──────────────────────────────────────
    bias = by_cat.copy()
    bias["link_method_none_pct"] = (
        100 * (1 - bias["event_rate_%"] / 100)
    ).round(1)
    bias.to_csv(OUT_DIR / "boamp_bias_report_enriched.csv", index=False)

    print(f"\nSaved:\n  {out_csv}")
    print(f"  {OUT_DIR / 'boamp_linking_stats_enriched.csv'}")
    print(f"  {OUT_DIR / 'boamp_bias_report_enriched.csv'}")


if __name__ == "__main__":
    main()
