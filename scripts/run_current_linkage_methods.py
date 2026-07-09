from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from current_boamp_lib import (
    FIGURES_LINKAGE,
    PROCESSED_CURRENT,
    PROXY_EVENT_NOTE,
    TABLES_LINKAGE,
    append_run_log,
    clean_siren,
    clean_siret,
    ensure_dirs,
    utc_now,
)
from src.visualization.academic_style import apply_academic_style, save_pdf_png

FEATURES = [
    "text_similarity",
    "cpv_score",
    "temporal_score",
    "buyer_quality_score",
    "composite_score",
    "candidate_rank",
    "score_margin",
    "source_generic_cpv",
    "candidate_generic_cpv",
    "missing_cpv_flag",
    "duration_imputed_flag",
]

M0_RULES = {
    "broad": {"text": 0.38, "composite": 0.52, "margin": None, "generic_allowed": True},
    "balanced": {"text": 0.50, "composite": 0.62, "margin": 0.03, "generic_allowed": True},
    "strict": {"text": 0.64, "composite": 0.70, "margin": 0.06, "generic_allowed": False},
}


def numeric_features(pairs: pd.DataFrame) -> pd.DataFrame:
    x = pairs[FEATURES].copy()
    for col in x.columns:
        if x[col].dtype == bool:
            x[col] = x[col].astype(int)
        x[col] = pd.to_numeric(x[col], errors="coerce")
    return x.fillna(0.0)


def current_silver_labels(pairs: pd.DataFrame) -> pd.Series:
    labels = (
        pairs["candidate_rank"].eq(1)
        & pairs["text_similarity"].ge(0.58)
        & pairs["composite_score"].ge(0.66)
        & pairs["temporal_score"].ge(0.45)
        & (pairs["cpv_score"].fillna(0.45).ge(0.4))
        & pairs["score_margin"].fillna(0.0).ge(0.025)
    )
    return labels.astype(int)


def select_best_links(scored: pd.DataFrame, score_col: str, threshold: float, method: str, variant: str) -> pd.DataFrame:
    d = scored[scored[score_col].ge(threshold)].copy()
    if d.empty:
        return d
    d = d.sort_values(["source_contract_id", score_col, "text_similarity"], ascending=[True, False, False])
    d = d.drop_duplicates("source_contract_id", keep="first")
    d["method"] = method
    d["variant"] = variant
    d["selection_score"] = d[score_col]
    return d


def apply_m0(pairs: pd.DataFrame, variant: str) -> pd.DataFrame:
    rule = M0_RULES[variant]
    mask = (
        pairs["candidate_rank"].eq(1)
        & pairs["text_similarity"].ge(rule["text"])
        & pairs["composite_score"].ge(rule["composite"])
    )
    if rule["margin"] is not None:
        mask &= pairs["score_margin"].fillna(1.0).ge(rule["margin"])
    if not rule["generic_allowed"]:
        mask &= ~(pairs["source_generic_cpv"].astype(bool) | pairs["candidate_generic_cpv"].astype(bool))
    d = pairs[mask].copy()
    d["method"] = "M0"
    d["variant"] = variant
    d["selection_score"] = d["composite_score"]
    return d


def build_survival_dataset(pop: pd.DataFrame, selected: pd.DataFrame, method_name: str, variant: str) -> pd.DataFrame:
    pop = pop[pop["eligible_for_linkage"].astype(str).str.lower().isin(["true", "1", "yes"])].copy()
    sel = selected.set_index("source_contract_id") if not selected.empty else pd.DataFrame()
    rows = []
    for row in pop.itertuples(index=False):
        contract_id = row.contract_id
        has = not selected.empty and contract_id in sel.index
        match = sel.loc[contract_id] if has else None
        event = int(has)
        observed = float(match["gap_months"]) if has else float(row.censoring_duration_months)
        rows.append(
            {
                "contract_id": contract_id,
                "source": "BOAMP_CURRENT",
                "buyer_key": row.buyer_key,
                "buyer_key_type": row.buyer_key_type,
                "buyer_name": row.buyer_name_raw,
                "SIREN": clean_siren(row.buyer_siren_enriched) if pd.notna(row.buyer_siren_enriched) else clean_siren(row.buyer_siren_clean),
                "SIRET": clean_siret(row.buyer_siret_clean),
                "segment": row.segment,
                "cpv_generic": bool(row.cpv_is_generic) if "cpv_is_generic" in pop.columns else False,
                "cpv_div2": row.cpv_div2,
                "source_date": row.source_date,
                "start_date": row.source_date,
                "declared_duration_months": row.declared_duration_months,
                "duration_imputed_flag": row.duration_imputed_flag,
                "estimated_end_date": row.estimated_end_date,
                "event": event,
                "observed_duration_months": round(observed, 2),
                "censoring_duration_months": round(observed, 2) if not event else np.nan,
                "renewal_duration_months": round(observed, 2) if event else np.nan,
                "renewal_contract_id": match["candidate_contract_id"] if has else None,
                "text_similarity": match["text_similarity"] if has else np.nan,
                "cpv_score": match["cpv_score"] if has else np.nan,
                "temporal_score": match["temporal_score"] if has else np.nan,
                "composite_score": match["composite_score"] if has else np.nan,
                "score_margin": match["score_margin"] if has else np.nan,
                "candidate_rank": match["candidate_rank"] if has else np.nan,
                "link_method": f"{method_name}_{variant}" if event else "none",
                "event_definition": f"{method_name}_{variant}; {PROXY_EVENT_NOTE}",
                "is_censored": int(not event),
            }
        )
    return pd.DataFrame(rows)


def metric_row(method: str, variant: str, selected: pd.DataFrame, eligible_n: int, labels: pd.Series, pairs: pd.DataFrame) -> dict:
    selected_pairs = pairs.index.isin(selected.index)
    y_true = labels
    y_pred = pd.Series(selected_pairs.astype(int), index=pairs.index)
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    events = selected["source_contract_id"].nunique() if not selected.empty else 0
    neg_accept = float(selected["candidate_rank"].gt(1).mean()) if not selected.empty else 0.0
    generic_share = float((selected["source_generic_cpv"].astype(bool) | selected["candidate_generic_cpv"].astype(bool)).mean()) if not selected.empty else 0.0
    return {
        "method": method,
        "variant": variant,
        "eligible_contracts": eligible_n,
        "event_count": events,
        "event_rate": events / eligible_n if eligible_n else 0.0,
        "censored_count": eligible_n - events,
        "negative_control_acceptance": neg_accept,
        "synthetic_benchmark_precision": float(p),
        "synthetic_benchmark_recall": float(r),
        "synthetic_benchmark_f1": float(f1),
        "generic_cpv_share": generic_share,
        "median_probability_or_score": float(selected["selection_score"].median()) if not selected.empty else np.nan,
        "median_margin": float(selected["score_margin"].median()) if not selected.empty else np.nan,
        "language_note": PROXY_EVENT_NOTE,
    }


def fit_probability_methods(pairs: pd.DataFrame, labels: pd.Series) -> dict[str, pd.Series]:
    x = numeric_features(pairs)
    groups = pairs["buyer_key"].astype(str)
    n_splits = min(5, max(2, groups.nunique()))
    cv = GroupKFold(n_splits=n_splits)
    probs: dict[str, pd.Series] = {}
    if labels.nunique() < 2 or labels.sum() < n_splits:
        pairs_default = pairs["composite_score"].clip(0, 1)
        probs["M1"] = pairs_default
        probs["M2"] = pairs_default
        return probs
    models = {
        "M1": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
        "M2": RandomForestClassifier(n_estimators=300, min_samples_leaf=4, class_weight="balanced_subsample", random_state=42, n_jobs=-1),
    }
    try:
        from lightgbm import LGBMClassifier

        models["M2"] = LGBMClassifier(n_estimators=250, learning_rate=0.035, num_leaves=15, class_weight="balanced", random_state=42, verbose=-1)
    except Exception:
        pass
    for name, model in models.items():
        pred = cross_val_predict(model, x, labels, cv=cv, groups=groups, method="predict_proba")[:, 1]
        probs[name] = pd.Series(pred, index=pairs.index)
    return probs


def main() -> None:
    ensure_dirs()
    pop = pd.read_csv(
        PROCESSED_CURRENT / "boamp_survival_population_base.csv",
        dtype={"buyer_siren_clean": str, "buyer_siret_clean": str, "buyer_siren_enriched": str, "buyer_key": str, "buyer_key_type": str},
        low_memory=False,
    )
    pairs = pd.read_csv(PROCESSED_CURRENT / "boamp_candidate_pairs_enriched.csv", low_memory=False)
    eligible_n = int(pop["eligible_for_linkage"].astype(str).str.lower().isin(["true", "1", "yes"]).sum())
    if pairs.empty:
        raise SystemExit("No candidate pairs were generated; cannot run linkage methods.")
    labels = current_silver_labels(pairs)
    pairs["current_synthetic_label"] = labels
    pairs["current_label_note"] = "current silver/synthetic benchmark label for method comparison only; not real BOAMP ground truth"

    selected_sets: dict[tuple[str, str], pd.DataFrame] = {}
    for variant in ["broad", "balanced", "strict"]:
        selected_sets[("M0", variant)] = apply_m0(pairs, variant)

    probs = fit_probability_methods(pairs, labels)
    pairs["m1_probability"] = probs["M1"]
    pairs["m2_probability"] = probs["M2"]
    selected_sets[("M1", "balanced")] = select_best_links(pairs, "m1_probability", 0.60, "M1", "balanced")
    selected_sets[("M2", "balanced")] = select_best_links(pairs, "m2_probability", 0.62, "M2", "balanced")

    metric_rows = []
    for (method, variant), selected in selected_sets.items():
        metric_rows.append(metric_row(method, variant, selected, eligible_n, labels, pairs))
        surv = build_survival_dataset(pop, selected, method, variant)
        out = PROCESSED_CURRENT / f"boamp_survival_method_{method.lower()}_{variant}.csv"
        surv.to_csv(out, index=False)
        if method == "M0" and variant == "balanced":
            surv.to_csv(PROCESSED_CURRENT / "boamp_survival_method_m0_balanced.csv", index=False)
        if method == "M2" and variant == "balanced":
            surv.to_csv(PROCESSED_CURRENT / "boamp_survival_method_m2_balanced.csv", index=False)

    pairs.to_csv(PROCESSED_CURRENT / "boamp_candidate_pairs_enriched_scored.csv", index=False)
    comparison = pd.DataFrame(metric_rows).sort_values(["method", "variant"])
    comparison.to_csv(TABLES_LINKAGE / "method_comparison_current_dataset.csv", index=False)

    m2 = comparison[(comparison["method"].eq("M2")) & (comparison["variant"].eq("balanced"))].iloc[0]
    m0 = comparison[(comparison["method"].eq("M0")) & (comparison["variant"].eq("balanced"))].iloc[0]
    selected_method, selected_variant = "M2", "balanced"
    reason = "M2 balanced retained as default because it is benchmark-feasible and interpretable on the current dataset."
    if (
        m2["synthetic_benchmark_f1"] + 0.02 < m0["synthetic_benchmark_f1"]
        or m2["event_count"] < max(30, 0.05 * eligible_n)
        or m2["negative_control_acceptance"] > m0["negative_control_acceptance"] + 0.05
    ):
        selected_method, selected_variant = "M0", "balanced"
        reason = "M0 balanced selected because M2 did not clearly improve current benchmark diagnostics."

    selected_row = comparison[(comparison["method"].eq(selected_method)) & (comparison["variant"].eq(selected_variant))].iloc[0].to_dict()
    recommendation = pd.DataFrame(
        [
            {
                "selected_method": selected_method,
                "selected_variant": selected_variant,
                "threshold": 0.62 if selected_method == "M2" else M0_RULES["balanced"],
                "selected_dataset_path": f"data/processed/boamp_current/boamp_survival_method_{selected_method.lower()}_{selected_variant}.csv",
                "eligible_contracts": selected_row["eligible_contracts"],
                "event_count": selected_row["event_count"],
                "event_rate": selected_row["event_rate"],
                "censoring_date": str(pop["censoring_date"].dropna().iloc[0]) if "censoring_date" in pop.columns else "",
                "main_evidence": reason,
                "limitations": "Synthetic/silver diagnostics guide method selection; real BOAMP precision/recall are not directly observed.",
                "language_note": PROXY_EVENT_NOTE,
            }
        ]
    )
    recommendation.to_csv(TABLES_LINKAGE / "final_method_recommendation_current_dataset.csv", index=False)
    recommendation.to_csv(TABLES_LINKAGE / "final_selected_event_definition_current.csv", index=False)

    apply_academic_style()
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    comparison["label"] = comparison["method"] + " " + comparison["variant"]
    ax.bar(comparison["label"], comparison["event_count"], color="#4C78A8")
    ax.set_title("Current Proxy Recurrence Events by Method")
    ax.set_ylabel("Event count")
    ax.tick_params(axis="x", labelrotation=25)
    save_pdf_png(fig, FIGURES_LINKAGE / "method_event_counts")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.hist(pairs["composite_score"], bins=35, alpha=0.65, label="M0 composite", color="#72B7B2")
    ax.hist(pairs["m2_probability"], bins=35, alpha=0.55, label="M2 probability", color="#F58518")
    ax.set_title("Current Linkage Score Distributions")
    ax.set_xlabel("Score / probability")
    ax.set_ylabel("Candidate pairs")
    ax.legend()
    save_pdf_png(fig, FIGURES_LINKAGE / "method_score_distributions")
    plt.close(fig)

    append_run_log(
        [
            "",
            f"## Current linkage methods - {utc_now()}",
            f"- Eligible contracts: {eligible_n}",
            f"- Selected method: {selected_method} {selected_variant}",
            f"- Event count: {selected_row['event_count']}",
            f"- Event rate: {selected_row['event_rate']:.4f}",
            "- Limitation: real BOAMP precision/recall are not directly observed.",
        ]
    )
    print("=== Current linkage methods ===")
    print(comparison.to_string(index=False))
    print("\nSelected:")
    print(recommendation.to_string(index=False))


if __name__ == "__main__":
    main()
