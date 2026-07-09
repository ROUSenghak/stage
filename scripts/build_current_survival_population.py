from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from current_boamp_lib import (
    FIGURES_DATA,
    PROCESSED_CURRENT,
    TABLES_DATA,
    append_run_log,
    current_study_end,
    duration_clean,
    ensure_dirs,
    month_diff,
    utc_now,
)
from src.visualization.academic_style import apply_academic_style, save_pdf_png

WINDOW_MONTHS = 6.0


def build_award_index(df: pd.DataFrame) -> dict[str, pd.Timestamp]:
    attr = df[
        df["nature"].eq("ATTRIBUTION")
        & df["annonce_lie"].notna()
        & df["date_attribution"].notna()
    ].copy()
    index: dict[str, pd.Timestamp] = {}
    for row in attr.itertuples(index=False):
        linked = str(row.annonce_lie).split("|")
        for ref in linked:
            ref = ref.strip()
            if not ref:
                continue
            date = pd.to_datetime(row.date_attribution, errors="coerce")
            if pd.notna(date):
                index[ref] = date.normalize()
    return index


def main() -> None:
    ensure_dirs()
    in_path = PROCESSED_CURRENT / "boamp_full_clean_enriched.csv"
    if not in_path.exists():
        raise SystemExit(f"Missing {in_path}; run build_boamp_current_enriched.py first.")
    df = pd.read_csv(in_path, dtype=str, low_memory=False)
    df["dateparution"] = pd.to_datetime(df["dateparution"], errors="coerce")
    study_end = current_study_end()
    award_index = build_award_index(df)

    ao = df[df["nature"].eq("APPEL_OFFRE")].copy()
    ao = ao[ao["dateparution"].notna() & ao["dateparution"].le(study_end)].copy()
    ao["source_date"] = [
        award_index.get(str(idweb).strip(), pub)
        for idweb, pub in zip(ao["idweb"], ao["dateparution"])
    ]
    ao["source_date_source"] = [
        "linked_attribution_date" if str(idweb).strip() in award_index else "publication_date"
        for idweb in ao["idweb"]
    ]
    dur = [duration_clean(v) for v in ao["duration_clean"]]
    ao["declared_duration_months"] = [x[0] for x in dur]
    ao["duration_imputed_flag"] = ao["duration_imputed_flag"].astype(str).str.lower().isin(["true", "1", "yes"]) | pd.Series([x[1] for x in dur], index=ao.index)
    ao["estimated_end_date"] = ao.apply(
        lambda r: pd.Timestamp(r["source_date"]) + pd.DateOffset(months=int(round(float(r["declared_duration_months"])))),
        axis=1,
    )
    ao["recurrence_window_close"] = ao["estimated_end_date"] + pd.DateOffset(months=int(WINDOW_MONTHS))
    ao["eligible_for_linkage"] = ao["recurrence_window_close"].le(study_end)
    ao["censoring_date"] = study_end
    ao["censoring_duration_months"] = [round(month_diff(s, study_end), 2) for s in ao["source_date"]]
    ao = ao[ao["censoring_duration_months"].gt(0)].copy()
    ao["contract_id"] = "BOAMP:" + ao["idweb"].astype(str)
    ao["segment"] = ao["category_label"].fillna("Unknown")

    out_cols = [
        "contract_id",
        "idweb",
        "notice_id",
        "buyer_key",
        "buyer_key_type",
        "buyer_name_raw",
        "buyer_name_normalized",
        "buyer_siren_clean",
        "buyer_siret_clean",
        "buyer_siren_enriched",
        "segment",
        "cpv_clean",
        "cpv_div2",
        "cpv_class4",
        "cpv_category5",
        "cpv_is_missing",
        "cpv_is_generic",
        "objet",
        "objet_clean",
        "source_date",
        "source_date_source",
        "declared_duration_months",
        "duration_imputed_flag",
        "estimated_end_date",
        "recurrence_window_close",
        "eligible_for_linkage",
        "censoring_date",
        "censoring_duration_months",
        "amount_clean",
        "type_procedure",
        "type_marche",
        "raw_trace_id",
    ]
    pop = ao[out_cols].copy()
    out_path = PROCESSED_CURRENT / "boamp_survival_population_base.csv"
    pop.to_csv(out_path, index=False)

    summary_rows = [
        {"stage": "all_current_notices", "rows": len(df), "note": "Downloaded and deduplicated current BOAMP notices"},
        {"stage": "appel_offre_before_date_filter", "rows": int(df["nature"].eq("APPEL_OFFRE").sum()), "note": "APPEL_OFFRE notices"},
        {"stage": "appel_offre_with_valid_source_date", "rows": len(ao), "note": "APPEL_OFFRE with publication/start date before censoring date"},
        {"stage": "eligible_for_linkage", "rows": int(pop["eligible_for_linkage"].sum()), "note": f"estimated_end_date + {WINDOW_MONTHS:g} months <= {study_end.date()}"},
    ]
    summary = pd.DataFrame(summary_rows)
    summary["study_start_date"] = pop["source_date"].min()
    summary["study_end_date"] = study_end.date().isoformat()
    summary["censoring_date"] = study_end.date().isoformat()
    summary["duration_rule"] = "declared duration, imputed to 48 months when missing/suspect"
    summary["attribution_date_refinement"] = "ATTRIBUTION annonce_lie date_attribution where available"
    summary.to_csv(TABLES_DATA / "analytical_population_summary.csv", index=False)

    apply_academic_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    bars = ax.bar(summary["stage"], summary["rows"], color=["#4C78A8", "#72B7B2", "#F58518", "#54A24B"])
    ax.set_title("Current BOAMP Analytical Population Funnel")
    ax.set_ylabel("Notices / contracts")
    ax.set_xlabel("")
    ax.tick_params(axis="x", labelrotation=20)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{int(bar.get_height()):,}", ha="center", va="bottom", fontsize=8)
    save_pdf_png(fig, FIGURES_DATA / "analytical_population_funnel")
    plt.close(fig)

    append_run_log(
        [
            "",
            f"## Current analytical population - {utc_now()}",
            f"- Study end/censoring date: {study_end.date()}",
            f"- APPEL_OFFRE rows: {len(pop)}",
            f"- Eligible for linkage: {int(pop['eligible_for_linkage'].sum())}",
            f"- Output: {out_path}",
        ]
    )
    print("=== Current analytical population ===")
    print(summary.to_string(index=False))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
