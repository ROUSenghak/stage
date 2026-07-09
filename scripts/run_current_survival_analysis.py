from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter, LogLogisticAFTFitter, LogNormalAFTFitter, WeibullAFTFitter
from lifelines.statistics import proportional_hazard_test

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from current_boamp_lib import FIGURES_SURVIVAL, PROCESSED_CURRENT, TABLES_LINKAGE, TABLES_SURVIVAL, append_run_log, ensure_dirs, utc_now
from src.visualization.academic_style import apply_academic_style, save_pdf_png

HORIZONS = [12, 24, 48, 60]


def load_selected() -> tuple[pd.DataFrame, str]:
    selected = pd.read_csv(TABLES_LINKAGE / "final_selected_event_definition_current.csv")
    path = Path(selected["selected_dataset_path"].iloc[0])
    if not path.is_absolute():
        path = Path.cwd() / path
    df = pd.read_csv(
        path,
        parse_dates=["start_date", "source_date", "estimated_end_date"],
        dtype={"SIREN": str, "SIRET": str, "buyer_key": str, "buyer_key_type": str},
        low_memory=False,
    )
    return df, f"{selected['selected_method'].iloc[0]} {selected['selected_variant'].iloc[0]}"


def prepare_model_df(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["event"] = pd.to_numeric(d["event"], errors="coerce").fillna(0).astype(int)
    d["observed_duration_months"] = pd.to_numeric(d["observed_duration_months"], errors="coerce")
    d["declared_duration_months"] = pd.to_numeric(d["declared_duration_months"], errors="coerce")
    d["duration_imputed_flag"] = d["duration_imputed_flag"].astype(str).str.lower().isin(["true", "1", "yes"]).astype(int)
    d["start_year"] = pd.to_datetime(d["start_date"], errors="coerce").dt.year
    top_segments = d["segment"].value_counts().head(5).index
    d["segment_model"] = d["segment"].where(d["segment"].isin(top_segments), "Other")
    model = d[["observed_duration_months", "event", "declared_duration_months", "duration_imputed_flag", "start_year", "segment_model", "buyer_key_type"]].dropna()
    model = pd.get_dummies(model, columns=["segment_model", "buyer_key_type"], drop_first=True, dtype=int)
    return model


def fit_aft_models(model_df: pd.DataFrame) -> tuple[pd.DataFrame, object, str]:
    rows = []
    best_model = None
    best_name = ""
    for name, cls in [("LogNormalAFT", LogNormalAFTFitter), ("WeibullAFT", WeibullAFTFitter), ("LogLogisticAFT", LogLogisticAFTFitter)]:
        try:
            model = cls(penalizer=0.1)
            model.fit(model_df, duration_col="observed_duration_months", event_col="event", show_progress=False)
            rows.append({"model": name, "AIC": model.AIC_, "log_likelihood": model.log_likelihood_, "n": len(model_df), "events": int(model_df["event"].sum())})
            if best_model is None or model.AIC_ < min(r["AIC"] for r in rows[:-1]):
                best_model = model
                best_name = name
        except Exception as exc:
            rows.append({"model": name, "AIC": np.nan, "log_likelihood": np.nan, "n": len(model_df), "events": int(model_df["event"].sum()), "error": str(exc)})
    return pd.DataFrame(rows).sort_values("AIC", na_position="last"), best_model, best_name


def risk_tables(df: pd.DataFrame, model_df: pd.DataFrame, aft_model, model_name: str) -> pd.DataFrame:
    features = model_df.drop(columns=["observed_duration_months", "event"])
    out = df.loc[model_df.index].copy()
    for h in [12, 24]:
        surv = aft_model.predict_survival_function(features, times=[h]).T.iloc[:, 0]
        out[f"p{h}"] = (1.0 - surv.to_numpy()).clip(0, 1)
    out["risk_tier"] = pd.cut(out["p12"], bins=[-0.01, 0.20, 0.40, 1.01], labels=["Low", "Medium", "High"])
    out["model_used"] = model_name
    out["main_risk_reason"] = np.where(out["duration_imputed_flag"].astype(str).str.lower().isin(["true", "1", "yes"]), "duration imputed", "model-estimated recurrence probability")
    return out


def main() -> None:
    ensure_dirs()
    apply_academic_style()
    df, selected_label = load_selected()
    model_df = prepare_model_df(df)

    kmf = KaplanMeierFitter()
    kmf.fit(df["observed_duration_months"], event_observed=df["event"], label=selected_label)
    summary = {
        "selected_method": selected_label,
        "eligible_contracts": len(df),
        "events": int(df["event"].sum()),
        "event_rate": float(df["event"].mean()),
        "median_survival_months": float(kmf.median_survival_time_) if np.isfinite(kmf.median_survival_time_) else np.inf,
    }
    for h in HORIZONS:
        summary[f"survival_{h}m"] = float(kmf.survival_function_at_times(h).iloc[0])
    pd.DataFrame([summary]).to_csv(TABLES_SURVIVAL / "survival_summary_current.csv", index=False)

    method_rows = []
    for name, path in {
        "M0 balanced": PROCESSED_CURRENT / "boamp_survival_method_m0_balanced.csv",
        "M2 balanced": PROCESSED_CURRENT / "boamp_survival_method_m2_balanced.csv",
    }.items():
        if path.exists():
            d = pd.read_csv(path)
            k = KaplanMeierFitter().fit(d["observed_duration_months"], event_observed=d["event"], label=name)
            method_rows.append({"method": name, "n": len(d), "events": int(d["event"].sum()), "event_rate": float(d["event"].mean()), "survival_24m": float(k.survival_function_at_times(24).iloc[0]), "survival_60m": float(k.survival_function_at_times(60).iloc[0])})
    pd.DataFrame(method_rows).to_csv(TABLES_SURVIVAL / "method_survival_comparison_current.csv", index=False)

    cox_results = []
    ph_rows = []
    try:
        cph = CoxPHFitter(penalizer=0.1)
        cph.fit(model_df, duration_col="observed_duration_months", event_col="event")
        cox = cph.summary.reset_index().rename(columns={"covariate": "variable", "index": "variable"})
        cox["c_index"] = cph.concordance_index_
        cox_results = cox
        ph = proportional_hazard_test(cph, model_df, time_transform="rank").summary.reset_index().rename(columns={"index": "variable"})
        ph_rows = ph
    except Exception as exc:
        cox_results = pd.DataFrame([{"variable": "MODEL_FAILED", "error": str(exc)}])
        ph_rows = pd.DataFrame([{"variable": "MODEL_FAILED", "error": str(exc)}])
    cox_results.to_csv(TABLES_SURVIVAL / "cox_results_current.csv", index=False)
    ph_rows.to_csv(TABLES_SURVIVAL / "cox_ph_diagnostics_current.csv", index=False)

    aft_comparison, aft_model, aft_name = fit_aft_models(model_df)
    aft_comparison.to_csv(TABLES_SURVIVAL / "aft_comparison_current.csv", index=False)
    risks = risk_tables(df, model_df, aft_model, aft_name)
    risks_out = risks[
        [
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
            "p12",
            "p24",
            "risk_tier",
            "main_risk_reason",
            "cpv_generic",
            "cpv_div2",
            "event",
            "observed_duration_months",
            "model_used",
        ]
    ].copy()
    risks_out.rename(columns={"p12": "p_renewal_12m", "p24": "p_renewal_24m"}, inplace=True)
    risks_out.to_csv(TABLES_SURVIVAL / "operational_risk_scores_current.csv", index=False)
    risks_out.sort_values("p_renewal_12m", ascending=False).head(50).to_csv(TABLES_SURVIVAL / "contract_risk_ranking_current.csv", index=False)
    buyer = risks_out.groupby(["buyer_key", "buyer_name"], dropna=False).agg(
        n_contracts=("contract_id", "count"),
        expected_renewals_12m=("p_renewal_12m", "sum"),
        expected_renewals_24m=("p_renewal_24m", "sum"),
        max_p12=("p_renewal_12m", "max"),
    ).reset_index().sort_values("expected_renewals_12m", ascending=False)
    buyer.to_csv(TABLES_SURVIVAL / "buyer_risk_ranking_current.csv", index=False)
    segment = risks_out.groupby("segment", dropna=False).agg(
        n_contracts=("contract_id", "count"),
        expected_renewals_12m=("p_renewal_12m", "sum"),
        expected_renewals_24m=("p_renewal_24m", "sum"),
        mean_p12=("p_renewal_12m", "mean"),
    ).reset_index().sort_values("expected_renewals_12m", ascending=False)
    segment.to_csv(TABLES_SURVIVAL / "segment_risk_ranking_current.csv", index=False)

    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    kmf.plot_survival_function(ax=ax, ci_show=True)
    ax.set_title(f"Current Kaplan-Meier Curve ({selected_label})")
    ax.set_xlabel("Observed duration (months)")
    ax.set_ylabel("Survival probability")
    save_pdf_png(fig, FIGURES_SURVIVAL / "km_curve_current")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    for name, path in {"M0 balanced": PROCESSED_CURRENT / "boamp_survival_method_m0_balanced.csv", "M2 balanced": PROCESSED_CURRENT / "boamp_survival_method_m2_balanced.csv"}.items():
        if path.exists():
            d = pd.read_csv(path)
            KaplanMeierFitter().fit(d["observed_duration_months"], d["event"], label=name).plot_survival_function(ax=ax, ci_show=False)
    ax.set_title("Current KM Comparison by Event Definition")
    ax.set_xlabel("Observed duration (months)")
    ax.set_ylabel("Survival probability")
    save_pdf_png(fig, FIGURES_SURVIVAL / "km_method_comparison_current")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    aft_comparison.dropna(subset=["AIC"]).plot.bar(x="model", y="AIC", ax=ax, color="#72B7B2", legend=False)
    ax.set_title("Current AFT Model Comparison")
    ax.set_ylabel("AIC")
    ax.set_xlabel("")
    save_pdf_png(fig, FIGURES_SURVIVAL / "aft_model_comparison_current")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.hist(risks_out["p_renewal_12m"], bins=35, color="#4C78A8", edgecolor="white")
    ax.set_title("Current 12-Month Recurrence Probability Distribution")
    ax.set_xlabel("p12")
    ax.set_ylabel("Contracts")
    save_pdf_png(fig, FIGURES_SURVIVAL / "p12_distribution_current")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    buyer.head(12).sort_values("expected_renewals_12m").plot.barh(x="buyer_name", y="expected_renewals_12m", ax=ax, color="#F58518", legend=False)
    ax.set_title("Top Current Buyer Risk")
    ax.set_xlabel("Expected recurrences in 12 months")
    save_pdf_png(fig, FIGURES_SURVIVAL / "top_buyer_risk_current")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    segment.head(12).sort_values("expected_renewals_12m").plot.barh(x="segment", y="expected_renewals_12m", ax=ax, color="#54A24B", legend=False)
    ax.set_title("Top Current Segment Risk")
    ax.set_xlabel("Expected recurrences in 12 months")
    save_pdf_png(fig, FIGURES_SURVIVAL / "top_segment_risk_current")
    plt.close(fig)

    append_run_log(
        [
            "",
            f"## Current survival analysis - {utc_now()}",
            f"- Selected method: {selected_label}",
            f"- Eligible contracts: {len(df)}",
            f"- Events: {int(df['event'].sum())}",
            f"- Event rate: {float(df['event'].mean()):.4f}",
            f"- Selected AFT model: {aft_name}",
        ]
    )
    print("=== Current survival analysis ===")
    print(pd.DataFrame([summary]).to_string(index=False))
    print(f"Selected AFT model: {aft_name}")


if __name__ == "__main__":
    main()
