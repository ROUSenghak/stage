"""BOAMP-only survival dataset builder.

Reads boamp_full_clean.csv and produces a survival-analysis-ready dataset
using only BOAMP data (no DECP).

Renewal linking logic
---------------------
Survival units  : APPEL_OFFRE notices only.
Start date      : award date from a linked ATTRIBUTION notice (via annonce_lie)
                  when available; publication date (dateparution) otherwise.
Grouping        : same buyer_key AND same cpv_div2.
Time window     : declared duration_clean ± 6 months (default 48 months when missing).
Text similarity : token Jaccard on objet field, threshold 0.20.
Scoring         : 0.7 × text_similarity + 0.3 × time_fit.
Censoring       : no renewal found → right-censored at 2024-12-31.

Outputs
-------
  data/processed/boamp_full_survival.csv
  data/processed/boamp_full_survival_report.md
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from utils import PROCESSED_DIR

STUDY_END = pd.Timestamp("2024-12-31")
WINDOW_MONTHS = 12.0
MIN_TEXT_SIM = 0.20
DEFAULT_DURATION = 48.0
MIN_DURATION = 1.0
MAX_DURATION = 120.0


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Award-date index from ATTRIBUTION notices ─────────────────────────────────

def build_award_index(boamp: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """Map idweb of an APPEL_OFFRE → award date from its linked ATTRIBUTION.

    When an ATTRIBUTION notice references the original call via annonce_lie,
    the award date is a more precise contract start than the publication date.
    """
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


# ── Renewal linker ────────────────────────────────────────────────────────────

def link_renewals(boamp: pd.DataFrame) -> pd.DataFrame:
    award_idx = build_award_index(boamp)

    # Work only on APPEL_OFFRE notices as survival units
    ao = boamp[boamp["nature"] == "APPEL_OFFRE"].copy()
    ao["pub_date"] = pd.to_datetime(ao["dateparution"], errors="coerce")
    ao = ao[ao["pub_date"].notna() & (ao["pub_date"] <= STUDY_END)].copy()

    # Refine start date using award date when available
    ao["start_date"] = ao.apply(
        lambda r: award_idx.get(str(r["idweb"]).strip(), r["pub_date"]),
        axis=1,
    )
    ao["_tokens"] = ao["objet"].map(_tokens)
    ao["_exp"] = ao["duration_clean"].map(_clamp)

    rows = []
    groups = ao.groupby(["buyer_key", "cpv_div2"], dropna=False, sort=False)

    for (buyer, cpv), grp in groups:
        grp = grp.sort_values("start_date")

        for _, src in grp.iterrows():
            start = src["start_date"]
            exp = src["_exp"]
            low = max(MIN_DURATION, exp - WINDOW_MONTHS)
            high = exp + WINDOW_MONTHS

            # Candidate: later notice from same buyer+CPV
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
                    "contract_id": f"BOAMP:{src['idweb']}",
                    "source": "BOAMP",
                    "buyer_key": buyer,
                    "cpv_div2": cpv,
                    "category_id": src.get("category_id"),
                    "category_label": src.get("category_label"),
                    "start_date": start.date().isoformat(),
                    "declared_duration_months": exp,
                    "event": 0,
                    "observed_duration_months": round(_month_diff(start, STUDY_END), 2),
                    "amount_clean": pd.to_numeric(src.get("amount_clean"), errors="coerce"),
                    "link_method": "none",
                    "renewal_contract_id": None,
                    "text_similarity": None,
                })
            else:
                pool["time_fit"] = (
                    1.0 - (pool["gap"] - exp).abs() / WINDOW_MONTHS
                ).clip(0.0, 1.0)
                pool["score"] = 0.7 * pool["sim"] + 0.3 * pool["time_fit"]
                best = pool.sort_values("score", ascending=False).iloc[0]
                rows.append({
                    "contract_id": f"BOAMP:{src['idweb']}",
                    "source": "BOAMP",
                    "buyer_key": buyer,
                    "cpv_div2": cpv,
                    "category_id": src.get("category_id"),
                    "category_label": src.get("category_label"),
                    "start_date": start.date().isoformat(),
                    "declared_duration_months": exp,
                    "event": 1,
                    "observed_duration_months": round(float(best["gap"]), 2),
                    "amount_clean": pd.to_numeric(src.get("amount_clean"), errors="coerce"),
                    "link_method": "boamp_jaccard",
                    "renewal_contract_id": f"BOAMP:{best['idweb']}",
                    "text_similarity": round(float(best["sim"]), 3),
                })

    df = pd.DataFrame(rows)
    return df[df["observed_duration_months"] > 0].copy()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    boamp = pd.read_csv(PROCESSED_DIR / "boamp_full_clean.csv", dtype=str)

    print(f"Loaded {len(boamp)} records from boamp_full_clean.csv")
    print(f"  APPEL_OFFRE: {(boamp['nature']=='APPEL_OFFRE').sum()}")
    print("Running renewal linker …")

    survival = link_renewals(boamp)

    out_csv = PROCESSED_DIR / "boamp_full_survival.csv"
    survival.to_csv(out_csv, index=False)

    n = len(survival)
    n_events = int(survival["event"].sum())
    event_rate = round(100 * n_events / n, 1) if n else 0.0

    by_cpv = (
        survival.groupby("cpv_div2", as_index=False)
        .agg(n=("contract_id", "count"), events=("event", "sum"))
    )
    by_cpv["event_rate_%"] = (100 * by_cpv["events"] / by_cpv["n"]).round(1)

    by_cat = (
        survival.groupby("category_label", as_index=False)
        .agg(n=("contract_id", "count"), events=("event", "sum"))
    )
    by_cat["event_rate_%"] = (100 * by_cat["events"] / by_cat["n"]).round(1)

    print("\n=== BOAMP full survival summary ===")
    print(f"Survival units (APPEL_OFFRE) : {n}")
    print(f"Linked renewals (events)     : {n_events}  ({event_rate}%)")
    print(f"Right-censored               : {n - n_events}  ({round(100 - event_rate, 1)}%)")
    print(f"\nMedian observed duration     : {survival['observed_duration_months'].median():.1f} months")
    if n_events > 0:
        print(f"Median event duration        : {survival.loc[survival['event']==1,'observed_duration_months'].median():.1f} months")
    print(f"\nBy CPV division:")
    print(by_cpv.to_string(index=False))
    print(f"\nBy category:")
    print(by_cat.sort_values("n", ascending=False).to_string(index=False))
    print(f"\nSaved: {out_csv}")

    # ── Markdown report ───────────────────────────────────────────────────────
    report_lines = [
        "# BOAMP-only Survival Dataset",
        "",
        "## Composition",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Survival units (APPEL_OFFRE) | {n} |",
        f"| Linked renewals (events) | {n_events} ({event_rate}%) |",
        f"| Right-censored | {n - n_events} ({round(100-event_rate,1)}%) |",
        f"| Median observed duration | {survival['observed_duration_months'].median():.1f} months |",
        "",
        "## Linking parameters",
        f"- Time window: declared duration ± {WINDOW_MONTHS} months (default {DEFAULT_DURATION} months when missing)",
        f"- Minimum Jaccard similarity: {MIN_TEXT_SIM}",
        f"- Scoring: 0.7 × text_similarity + 0.3 × time_fit",
        f"- Start date: award date (via annonce_lie) when available, publication date otherwise",
        "",
        "## By CPV division",
        "| cpv_div2 | n | events | event_rate_% |",
        "|----------|---|--------|--------------|",
        *[f"| {row['cpv_div2']} | {row['n']} | {row['events']} | {row['event_rate_%']} |"
          for _, row in by_cpv.iterrows()],
        "",
        "## By category",
        "| category_label | n | events | event_rate_% |",
        "|----------------|---|--------|--------------|",
        *[f"| {row['category_label']} | {row['n']} | {row['events']} | {row['event_rate_%']} |"
          for _, row in by_cat.sort_values("n", ascending=False).iterrows()],
        "",
        "## Known limitations",
        "1. buyer_key is name-based for 90%+ of records (SIRET coverage ~9% in BOAMP).",
        "   Name normalization may split one real buyer into multiple keys (e.g. 'Ville de Nantes' vs 'Nantes Metropole').",
        "2. Jaccard linking on short objet strings can produce false positives for",
        "   generic descriptions ('prestations informatiques', 'maintenance informatique').",
        "3. Contracts started in 2021-2024 are almost certainly right-censored: with",
        "   typical 48-month durations, their renewals fall after the 2024-12-31 study end.",
    ]

    report_path = PROCESSED_DIR / "boamp_full_survival_report.md"
    report_path.write_text("\n".join(report_lines))
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    main()
