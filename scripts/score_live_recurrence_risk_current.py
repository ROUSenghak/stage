from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import TABLES_SURVIVAL, append_run_log, ensure_dirs, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prediction-date", default=None, help="Optional YYYY-MM-DD scoring date recorded in outputs.")
    args = parser.parse_args()
    ensure_dirs()
    risk_path = TABLES_SURVIVAL / "operational_risk_scores_current.csv"
    if not risk_path.exists():
        raise SystemExit("Missing operational_risk_scores_current.csv; run run_current_survival_analysis.py first.")
    df = pd.read_csv(
        risk_path,
        parse_dates=["source_date", "estimated_end_date"],
        dtype={"SIREN": str, "SIRET": str, "buyer_key": str, "buyer_key_type": str},
        low_memory=False,
    )
    prediction_date = pd.Timestamp(args.prediction_date) if args.prediction_date else pd.Timestamp.today().normalize()
    df["prediction_date"] = prediction_date.date().isoformat()
    df["data_quality_flags"] = ""
    df.loc[df["buyer_key_type"].eq("NAME"), "data_quality_flags"] += "name_fallback_buyer_key;"
    df.loc[df["SIREN"].isna() & df["SIRET"].isna(), "data_quality_flags"] += "missing_siren_siret;"
    df.loc[df["declared_duration_months"].isna(), "data_quality_flags"] += "missing_duration;"
    df.loc[df["cpv_div2"].isna(), "data_quality_flags"] += "missing_cpv;"
    if "cpv_generic" not in df.columns:
        df["cpv_generic"] = False
    df["main_risk_reason"] = df["main_risk_reason"].fillna("model-estimated recurrence probability")

    live_cols = [
        "contract_id",
        "buyer_key",
        "buyer_name",
        "SIREN",
        "SIRET",
        "buyer_key_type",
        "segment",
        "source_date",
        "declared_duration_months",
        "estimated_end_date",
        "p_renewal_12m",
        "p_renewal_24m",
        "risk_tier",
        "main_risk_reason",
        "cpv_generic",
        "data_quality_flags",
        "prediction_date",
    ]
    live = df[live_cols].sort_values(["p_renewal_12m", "contract_id"], ascending=[False, True])
    live.to_csv(TABLES_SURVIVAL / "live_contract_risk_scores_current.csv", index=False)
    buyer = live.groupby(["buyer_key", "buyer_name"], dropna=False).agg(
        n_live_contracts=("contract_id", "count"),
        expected_renewals_12m=("p_renewal_12m", "sum"),
        expected_renewals_24m=("p_renewal_24m", "sum"),
        max_p12=("p_renewal_12m", "max"),
        high_risk_contracts=("risk_tier", lambda s: (s == "High").sum()),
    ).reset_index().sort_values("expected_renewals_12m", ascending=False)
    buyer.to_csv(TABLES_SURVIVAL / "live_buyer_risk_ranking_current.csv", index=False)
    segment = live.groupby("segment", dropna=False).agg(
        n_live_contracts=("contract_id", "count"),
        expected_renewals_12m=("p_renewal_12m", "sum"),
        expected_renewals_24m=("p_renewal_24m", "sum"),
        mean_p12=("p_renewal_12m", "mean"),
    ).reset_index().sort_values("expected_renewals_12m", ascending=False)
    segment.to_csv(TABLES_SURVIVAL / "live_segment_risk_ranking_current.csv", index=False)
    append_run_log(
        [
            "",
            f"## Current live scoring - {utc_now()}",
            f"- Prediction date: {prediction_date.date()}",
            f"- Live contracts: {len(live)}",
            f"- Expected 12-month recurrences: {live['p_renewal_12m'].sum():.2f}",
        ]
    )
    print("=== Current live scoring ===")
    print(f"Contracts: {len(live)}")
    print(f"Expected 12-month recurrences: {live['p_renewal_12m'].sum():.2f}")


if __name__ == "__main__":
    main()
