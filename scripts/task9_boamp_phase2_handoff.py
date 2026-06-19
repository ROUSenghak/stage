"""TASK 9 — BOAMP-only Phase 2 handoff dataset.

Standardizes the BOAMP renewal-linking notebook output into a single
analysis-ready CSV under data/processed/ so the repository has one explicit
BOAMP-only modeling handoff for Phase 2.

Input
-----
  boamp_renewal_linking_quality/outputs/boamp_renewal_links.csv

Outputs
-------
  data/processed/boamp_phase2_survival.csv
  data/processed/boamp_phase2_survival_report.md

Notes
-----
The notebook output already contains one row per eligible APPEL_OFFRE.
This task does not relink notices; it validates the notebook output,
standardizes column names, and makes censoring explicit.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils import PROCESSED_DIR, ROOT

NOTEBOOK_OUTPUT = (
    ROOT
    / "boamp_renewal_linking_quality"
    / "outputs"
    / "boamp_renewal_links.csv"
)


def main() -> None:
    if not NOTEBOOK_OUTPUT.exists():
        raise SystemExit(
            "Notebook output not found: "
            f"{NOTEBOOK_OUTPUT}\n"
            "Run boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb first."
        )

    df = pd.read_csv(NOTEBOOK_OUTPUT)

    required = {
        "contract_id",
        "contract_start",
        "declared_duration_months",
        "event",
        "observed_duration_months",
        "renewal_contract_id",
        "buyer_key",
        "cpv_div2",
        "category_label",
        "link_method",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing required notebook-output columns: {missing}")

    if df["contract_id"].duplicated().any():
        dupes = int(df["contract_id"].duplicated().sum())
        raise SystemExit(f"Notebook output has duplicated contract_id values: {dupes}")

    df["event"] = pd.to_numeric(df["event"], errors="coerce").fillna(0).astype(int)
    df["observed_duration_months"] = pd.to_numeric(
        df["observed_duration_months"], errors="coerce"
    )
    df["declared_duration_months"] = pd.to_numeric(
        df["declared_duration_months"], errors="coerce"
    )

    if not df["event"].isin([0, 1]).all():
        raise SystemExit("event column must contain only 0/1 values")
    if df["contract_start"].isna().any():
        raise SystemExit("contract_start contains missing values")
    if df["observed_duration_months"].isna().any():
        raise SystemExit("observed_duration_months contains missing values")
    if (df["observed_duration_months"] <= 0).any():
        raise SystemExit("observed_duration_months must be strictly positive")
    if df.loc[df["event"] == 1, "renewal_contract_id"].isna().any():
        raise SystemExit("event=1 rows must have a renewal_contract_id")

    handoff = pd.DataFrame(
        {
            "contract_id": df["contract_id"],
            "source": "BOAMP",
            "buyer_key": df["buyer_key"],
            "cpv_div2": df["cpv_div2"],
            "category_label": df["category_label"],
            "start_date": df["contract_start"],
            "declared_duration_months": df["declared_duration_months"],
            "event": df["event"],
            "observed_duration_months": df["observed_duration_months"],
            "censoring_duration_months": df["observed_duration_months"].where(
                df["event"] == 0
            ),
            "renewal_duration_months": df["observed_duration_months"].where(
                df["event"] == 1
            ),
            "renewal_contract_id": df["renewal_contract_id"],
            "amount_clean": pd.to_numeric(df.get("amount_clean"), errors="coerce"),
            "type_procedure": df.get("type_procedure"),
            "type_marche": df.get("type_marche"),
            "dur_was_imputed": df.get("dur_was_imputed"),
            "estimated_end_date": df.get("estimated_end_date"),
            "start_date_source": df.get("start_date_source"),
            "link_method": df["link_method"],
            "composite_score": pd.to_numeric(df.get("composite_score"), errors="coerce"),
            "text_similarity": pd.to_numeric(df.get("text_similarity"), errors="coerce"),
            "cpv_match_score": pd.to_numeric(df.get("cpv_match_score"), errors="coerce"),
            "temporal_score": pd.to_numeric(df.get("temporal_score"), errors="coerce"),
            "flag_amount_zero": df.get("flag_amount_zero"),
            "flag_amount_tiny": df.get("flag_amount_tiny"),
            "flag_amount_ceiling": df.get("flag_amount_ceiling"),
            # Strict high-confidence diagnostics (TASK 10). Passed through unchanged;
            # absent if task10 has not been run yet.
            "best_composite_score": pd.to_numeric(
                df.get("best_composite_score"), errors="coerce"
            ),
            "second_best_composite_score": pd.to_numeric(
                df.get("second_best_composite_score"), errors="coerce"
            ),
            "score_margin": pd.to_numeric(df.get("score_margin"), errors="coerce"),
            "n_candidates_for_source": pd.to_numeric(
                df.get("n_candidates_for_source"), errors="coerce"
            ),
            "single_candidate_match": df.get("single_candidate_match"),
            "high_confidence_strict": df.get("high_confidence_strict"),
        }
    )

    out_csv = PROCESSED_DIR / "boamp_phase2_survival.csv"
    handoff.to_csv(out_csv, index=False)

    n = len(handoff)
    n_events = int(handoff["event"].sum())
    n_censored = n - n_events
    rate = round(100 * n_events / n, 2) if n else 0.0

    by_cat = (
        handoff.groupby("category_label", dropna=False, as_index=False)
        .agg(n=("contract_id", "count"), events=("event", "sum"))
    )
    by_cat["event_rate_%"] = (100 * by_cat["events"] / by_cat["n"]).round(2)

    report_lines = [
        "# BOAMP-only Phase 2 Handoff Dataset",
        "",
        "This file is the official BOAMP-only modeling handoff for Phase 2.",
        "It is derived from the notebook renewal-linking output and contains one row",
        "per eligible APPEL_OFFRE notice.",
        "",
        "## Composition",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Contracts | {n} |",
        f"| Events (plausible renewals) | {n_events} ({rate}%) |",
        f"| Right-censored | {n_censored} ({round(100 - rate, 2)}%) |",
        "",
        "## Variable semantics",
        "- `event = 1`: a plausible renewal link was found under the BOAMP-only algorithm.",
        "- `event = 0`: no renewal link was observed under the algorithm before study end.",
        "- `renewal_duration_months`: observed gap for linked contracts only.",
        "- `censoring_duration_months`: observed time from start date to study end for censored contracts only.",
        "",
        "## By category",
        "| category_label | n | events | event_rate_% |",
        "|----------------|---|--------|--------------|",
        *[
            f"| {row['category_label']} | {row['n']} | {row['events']} | {row['event_rate_%']} |"
            for _, row in by_cat.sort_values("n", ascending=False).iterrows()
        ],
    ]
    out_report = PROCESSED_DIR / "boamp_phase2_survival_report.md"
    out_report.write_text("\n".join(report_lines))

    print("=== TASK 9 summary ===")
    print(f"Loaded notebook output : {NOTEBOOK_OUTPUT}")
    print(f"Contracts              : {n}")
    print(f"Events                 : {n_events} ({rate}%)")
    print(f"Right-censored         : {n_censored} ({round(100 - rate, 2)}%)")
    print(f"Saved CSV              : {out_csv}")
    print(f"Saved report           : {out_report}")


if __name__ == "__main__":
    main()