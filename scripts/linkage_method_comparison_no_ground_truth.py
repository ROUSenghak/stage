from __future__ import annotations

import json
import math
import os
import re
import warnings
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-stage-1")
warnings.filterwarnings("ignore")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from lifelines import CoxPHFitter, KaplanMeierFitter, LogLogisticAFTFitter, LogNormalAFTFitter, WeibullAFTFitter
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize as sk_normalize


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

VALIDATION_TABLES = ROOT / "reports" / "tables" / "validation"
VALIDATION_FIGURES = ROOT / "reports" / "figures" / "validation"
SURVIVAL_TABLES = ROOT / "reports" / "tables" / "survival"
PROCESSED = ROOT / "data" / "processed"
SYNTHETIC = ROOT / "data" / "synthetic"
REAL_OUT = ROOT / "boamp_renewal_linking_quality" / "outputs"
EVENT_VALIDATION = ROOT / "event_validation" / "outputs"
ROBUSTNESS = ROOT / "validation_robustness" / "outputs"

for path in [VALIDATION_TABLES, VALIDATION_FIGURES, SURVIVAL_TABLES]:
    path.mkdir(parents=True, exist_ok=True)

GENERIC_CPV_CODES = {"72000000", "48000000", "32000000", "35000000"}
FEATURES = [
    "text_similarity",
    "cpv_score",
    "generic_cpv_flag",
    "temporal_score",
    "time_gap_months",
    "composite_score",
    "rank",
    "margin",
    "buyer_frequency",
    "missing_cpv_flag",
    "missing_duration_flag",
]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, low_memory=False, **kwargs)


def clean_cpv(value) -> str | None:
    if pd.isna(value):
        return None
    text = re.sub(r"\.0$", "", str(value).strip())
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    return digits[:8].zfill(8)


def is_generic_cpv(value) -> bool:
    cpv = clean_cpv(value)
    return bool(cpv and (cpv in GENERIC_CPV_CODES or cpv.endswith("000000")))


def cpv_score(src_cpv, cand_cpv) -> float:
    src = clean_cpv(src_cpv)
    cand = clean_cpv(cand_cpv)
    if src is None or cand is None:
        return np.nan
    same_div = src[:2] == cand[:2]
    if is_generic_cpv(src) or is_generic_cpv(cand):
        return 0.20 if same_div else 0.0
    if src[:8] == cand[:8]:
        return 1.0
    if src[:5] == cand[:5]:
        return 0.8
    if src[:4] == cand[:4]:
        return 0.6
    if src[:3] == cand[:3]:
        return 0.4
    return 0.2 if same_div else 0.0


def composite_score(text_score, cpv_s, temporal_s, buyer_s=1.0) -> float:
    if pd.isna(cpv_s):
        return (0.40 * text_score + 0.20 * temporal_s + 0.15 * buyer_s) / 0.75
    return 0.40 * text_score + 0.25 * cpv_s + 0.20 * temporal_s + 0.15 * buyer_s


def month_gap(start, end) -> float:
    return (pd.Timestamp(end) - pd.Timestamp(start)).days / 30.44


def temporal_score(gap_months, expected_duration, W=6) -> float:
    if pd.isna(gap_months):
        return np.nan
    duration = 48.0 if pd.isna(expected_duration) else float(expected_duration)
    return float(np.clip(1.0 - abs(float(gap_months) - duration) / float(W), 0.0, 1.0))


def rank_and_margin(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    out = df.copy()
    out = out.sort_values(["source_contract_id", score_col, "text_similarity"], ascending=[True, False, False])
    out["rank"] = out.groupby("source_contract_id").cumcount() + 1
    top_two = out.loc[out["rank"].le(2), ["source_contract_id", "rank", score_col]]
    top_two = top_two.pivot(index="source_contract_id", columns="rank", values=score_col)
    margins = (top_two.get(1) - top_two.get(2)).rename("source_margin")
    out = out.merge(margins, on="source_contract_id", how="left")
    out["margin"] = np.where(out["rank"].eq(1), out["source_margin"], np.nan)
    out = out.drop(columns=["source_margin"])
    return out


def normalize_manual_label(value) -> str | float:
    if pd.isna(value):
        return np.nan
    value = str(value)
    if value == "true_positive":
        return "true_positive"
    if value == "false_positive":
        return "false_positive"
    if value == "uncertain":
        return "uncertain"
    return value


def make_real_pairs(real_candidates: pd.DataFrame, manual: pd.DataFrame | None) -> pd.DataFrame:
    d = real_candidates.copy()
    d["source_contract_id"] = "BOAMP:" + d["src_idweb"].astype(str)
    d["candidate_contract_id"] = "BOAMP:" + d["cand_idweb"].astype(str)
    d["buyer_key"] = d["src_buyer_key"]
    d["text_similarity"] = pd.to_numeric(d["text_similarity_score"], errors="coerce")
    d["cpv_score"] = pd.to_numeric(d["cpv_match_score"], errors="coerce")
    d["generic_cpv_flag"] = d["src_cpv"].map(is_generic_cpv) | d["cand_cpv"].map(is_generic_cpv)
    d["temporal_score"] = pd.to_numeric(d["temporal_proximity_score"], errors="coerce")
    d["time_gap_months"] = pd.to_numeric(d["gap_months"], errors="coerce")
    d["composite_score"] = pd.to_numeric(d["composite_score"], errors="coerce")
    d["missing_cpv_flag"] = d["src_cpv"].isna() | d["cand_cpv"].isna()
    d["missing_duration_flag"] = d["src_duration_months"].isna()
    d["candidate_pair_dataset"] = "real_boamp"
    d["scenario"] = "real_boamp"
    d["synthetic_true_match"] = np.nan
    d["synthetic_true_event"] = np.nan
    d["manual_audit_label"] = np.nan
    d["manual_pair_label"] = np.nan
    d["source_start_date"] = d["src_contract_start"]
    d["candidate_start_date"] = d["cand_contract_start"]
    d = rank_and_margin(d, "composite_score")
    buyer_frequency = d.groupby("buyer_key")["source_contract_id"].transform("nunique")
    d["buyer_frequency"] = buyer_frequency
    d["negative_control"] = d["rank"].gt(1)

    if manual is not None and not manual.empty:
        m = manual.copy()
        m = m[m["renewal_contract_id"].notna()].copy()
        m["source_contract_id"] = m["contract_id"].astype(str)
        m["candidate_contract_id"] = m["renewal_contract_id"].astype(str)
        m["manual_audit_label"] = m["manual_error_type"].map(normalize_manual_label)
        label_map = {"true_positive": 1.0, "false_positive": 0.0}
        m["manual_pair_label"] = m["manual_audit_label"].map(label_map)
        d = d.merge(
            m[["source_contract_id", "candidate_contract_id", "manual_audit_label", "manual_pair_label"]],
            on=["source_contract_id", "candidate_contract_id"],
            how="left",
            suffixes=("", "_manual"),
        )
        for col in ["manual_audit_label", "manual_pair_label"]:
            d[col] = d[f"{col}_manual"].combine_first(d[col])
            d = d.drop(columns=[f"{col}_manual"])

    return d


def make_calibrated_selected(calibrated: pd.DataFrame, real_pairs: pd.DataFrame, variant: str) -> pd.DataFrame:
    d = calibrated.copy()
    d["source_contract_id"] = "BOAMP:" + d["src_idweb"].astype(str)
    d["candidate_contract_id"] = "BOAMP:" + d["cand_idweb"].astype(str)
    d["buyer_key"] = d["src_buyer_key"]
    d["text_similarity"] = pd.to_numeric(d.get("text_similarity_rule", d.get("text_similarity_score")), errors="coerce")
    d["cpv_score"] = pd.to_numeric(d.get("cpv_match_score_rule", d.get("cpv_match_score")), errors="coerce")
    d["generic_cpv_flag"] = d["source_generic_cpv"].fillna(False).astype(bool) | d["candidate_generic_cpv"].fillna(False).astype(bool)
    d["temporal_score"] = pd.to_numeric(d.get("temporal_score_rule", d.get("temporal_proximity_score")), errors="coerce")
    d["time_gap_months"] = pd.to_numeric(d.get("gap_months_rule", d.get("gap_months")), errors="coerce")
    d["composite_score"] = pd.to_numeric(d.get("composite_score_rule", d.get("composite_score")), errors="coerce")
    d["rank"] = pd.to_numeric(d.get("rank", 1), errors="coerce").fillna(1).astype(int)
    d["margin"] = pd.to_numeric(d.get("score_margin_rule", d.get("score_margin")), errors="coerce")
    d["candidate_pair_dataset"] = "real_boamp"
    d["scenario"] = "real_boamp"
    d["negative_control"] = False
    d["source_start_date"] = d["src_contract_start"]
    d["candidate_start_date"] = d["cand_contract_start"]
    d["missing_cpv_flag"] = d["src_cpv"].isna() | d["cand_cpv"].isna()
    d["missing_duration_flag"] = d["src_duration_months"].isna()
    d["buyer_frequency"] = d.groupby("buyer_key")["source_contract_id"].transform("nunique")
    cols = [
        "source_contract_id",
        "candidate_contract_id",
        "manual_audit_label",
        "manual_pair_label",
        "m1_match_probability",
        "m2_match_probability",
    ]
    enrich = real_pairs[[c for c in cols if c in real_pairs.columns]].copy()
    d = d.merge(enrich, on=["source_contract_id", "candidate_contract_id"], how="left")
    d["calibrated_variant"] = variant
    return d


def make_synthetic_pairs(notices: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    notices = notices.copy()
    notices["start_date"] = pd.to_datetime(notices["start_date"], errors="coerce")
    notices["estimated_end_date"] = pd.to_datetime(notices["estimated_end_date"], errors="coerce")
    notices["object_text"] = notices["object"].fillna("").astype(str)
    tfidf = TfidfVectorizer(min_df=1, ngram_range=(1, 2), strip_accents="unicode", lowercase=True)
    matrix = sk_normalize(tfidf.fit_transform(notices["object_text"]))
    loc = {notice_id: i for i, notice_id in enumerate(notices["notice_id"])}
    truth_map = truth.set_index("source_id")["true_candidate_id"].to_dict()
    event_map = truth.set_index("source_id")["true_event"].to_dict()

    rows = []
    for (scenario, buyer_key), group in notices.groupby(["scenario", "buyer_key"], dropna=False):
        sources = group[group["role"].eq("source")]
        candidates = group[group["role"].eq("candidate")]
        if sources.empty or candidates.empty:
            continue
        for _, src in sources.iterrows():
            duration = 48.0 if pd.isna(src["declared_duration_months"]) else float(src["declared_duration_months"])
            start = src["start_date"]
            if pd.isna(start):
                continue
            cands = candidates[candidates["start_date"].gt(start)].copy()
            if cands.empty:
                continue
            cands["time_gap_months"] = (cands["start_date"] - start).dt.days / 30.44
            cands = cands[(cands["time_gap_months"] - duration).abs().le(12)]
            if cands.empty:
                continue
            s_idx = loc[src["notice_id"]]
            for _, cand in cands.iterrows():
                c_idx = loc[cand["notice_id"]]
                text_s = float(matrix[s_idx].multiply(matrix[c_idx]).sum())
                cpv_s = cpv_score(src["cpv"], cand["cpv"])
                temp_s = temporal_score(cand["time_gap_months"], duration, W=6)
                comp_s = composite_score(text_s, cpv_s, temp_s)
                rows.append(
                    {
                        "source_contract_id": src["notice_id"],
                        "candidate_contract_id": cand["notice_id"],
                        "buyer_key": buyer_key,
                        "text_similarity": text_s,
                        "cpv_score": cpv_s,
                        "generic_cpv_flag": is_generic_cpv(src["cpv"]) or is_generic_cpv(cand["cpv"]),
                        "temporal_score": temp_s,
                        "time_gap_months": float(cand["time_gap_months"]),
                        "composite_score": comp_s,
                        "synthetic_true_match": cand["notice_id"] == truth_map.get(src["notice_id"]),
                        "synthetic_true_event": event_map.get(src["notice_id"], 0),
                        "candidate_pair_dataset": "synthetic",
                        "scenario": scenario,
                        "negative_control": cand["notice_id"] != truth_map.get(src["notice_id"]),
                        "manual_audit_label": np.nan,
                        "manual_pair_label": np.nan,
                        "source_start_date": src["start_date"],
                        "candidate_start_date": cand["start_date"],
                        "missing_cpv_flag": pd.isna(src["cpv"]) or pd.isna(cand["cpv"]),
                        "missing_duration_flag": bool(src.get("duration_missing_flag", 0) == 1 or pd.isna(src["declared_duration_months"])),
                    }
                )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("No synthetic candidate pairs generated.")
    out = rank_and_margin(out, "composite_score")
    out["buyer_frequency"] = out.groupby("buyer_key")["source_contract_id"].transform("nunique")
    return out


def method_metric_from_predictions(
    source_truth: pd.DataFrame,
    predicted: pd.DataFrame,
    source_col: str = "source_contract_id",
    candidate_col: str = "candidate_contract_id",
) -> dict:
    pred = predicted[[source_col, candidate_col]].copy()
    pred["predicted_event"] = 1
    work = source_truth.merge(pred, on=source_col, how="left")
    work["predicted_event"] = work["predicted_event"].fillna(0).astype(int)
    work["predicted_candidate_id"] = work[candidate_col]
    work["is_tp"] = work["true_event"].eq(1) & work["predicted_event"].eq(1) & (work["predicted_candidate_id"] == work["true_candidate_id"])
    work["is_fp"] = work["predicted_event"].eq(1) & ~work["is_tp"]
    work["is_fn"] = work["true_event"].eq(1) & ~work["is_tp"]
    work["is_tn"] = work["true_event"].eq(0) & work["predicted_event"].eq(0)
    tp = int(work["is_tp"].sum())
    fp = int(work["is_fp"].sum())
    fn = int(work["is_fn"].sum())
    tn = int(work["is_tn"].sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "precision": precision,
        "recall": recall,
        "F1": f1,
        "event_count": int(work["predicted_event"].sum()),
        "event_rate": float(work["predicted_event"].mean()),
    }


def select_by_rule(pairs: pd.DataFrame, text_threshold, composite_threshold, margin_threshold=None) -> pd.DataFrame:
    d = pairs.copy()
    top = d[d["rank"].eq(1)].copy()
    keep = top["text_similarity"].ge(float(text_threshold))
    if str(composite_threshold).lower() != "none":
        keep &= top["composite_score"].ge(float(composite_threshold))
    if margin_threshold is not None and str(margin_threshold).lower() != "none":
        keep &= top["margin"].fillna(1.0).ge(float(margin_threshold))
    return top[keep].copy()


def predict_from_score(pairs: pd.DataFrame, score_col: str, threshold: float) -> pd.DataFrame:
    d = pairs.copy()
    d = d.sort_values(["source_contract_id", score_col, "text_similarity"], ascending=[True, False, False])
    top = d.groupby("source_contract_id", as_index=False).head(1)
    return top[top[score_col].ge(threshold)].copy()


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df[FEATURES].copy()
    for col in FEATURES:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def fit_probability_model(train_df: pd.DataFrame, y: pd.Series, sample_weight=None) -> Pipeline:
    transformer = ColumnTransformer(
        [("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), FEATURES)],
        remainder="drop",
    )
    model = LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")
    pipe = Pipeline([("prep", transformer), ("model", model)])
    fit_kwargs = {}
    if sample_weight is not None:
        fit_kwargs["model__sample_weight"] = sample_weight
    pipe.fit(feature_frame(train_df), y.astype(int), **fit_kwargs)
    return pipe


def add_probabilities(synthetic_pairs: pd.DataFrame, real_pairs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    syn = synthetic_pairs.copy()
    real = real_pairs.copy()
    y = syn["synthetic_true_match"].fillna(False).astype(int)
    groups = syn["source_contract_id"].astype(str)
    cv = GroupKFold(n_splits=5)
    base_pipe = fit_probability_model(syn, y)
    syn["m1_match_probability"] = cross_val_predict(
        base_pipe, feature_frame(syn), y, groups=groups, cv=cv, method="predict_proba"
    )[:, 1]
    final_m1 = fit_probability_model(syn, y)
    real["m1_match_probability"] = final_m1.predict_proba(feature_frame(real))[:, 1]

    manual_train = real[real["manual_pair_label"].notna()].copy()
    model_notes = {
        "m1_model": "LogisticRegression classifier trained on synthetic benchmark pair labels; Splink and recordlinkage were unavailable.",
        "m2_model": "Active-learning-assisted LogisticRegression using synthetic labels plus mapped manual TP/FP accepted-link labels where available.",
        "manual_training_pairs": int(len(manual_train)),
    }

    if len(manual_train) >= 10 and manual_train["manual_pair_label"].nunique() == 2:
        m2_train = pd.concat([syn, manual_train], ignore_index=True)
        m2_y = pd.concat([y, manual_train["manual_pair_label"].astype(int)], ignore_index=True)
        weights = np.ones(len(m2_train))
        weights[len(syn) :] = 2.0
        final_m2 = fit_probability_model(m2_train, m2_y, sample_weight=weights)
        syn["m2_match_probability"] = syn["m1_match_probability"]
        real["m2_match_probability"] = final_m2.predict_proba(feature_frame(real))[:, 1]
    else:
        syn["m2_match_probability"] = syn["m1_match_probability"]
        real["m2_match_probability"] = real["m1_match_probability"]
        model_notes["m2_model"] += " Manual labels were insufficient for a separate fit, so probabilities fall back to M1."
    return syn, real, model_notes


def synthetic_metrics_for_method(source_truth: pd.DataFrame, pairs: pd.DataFrame, method: str, variant: str, selected: pd.DataFrame) -> list[dict]:
    rows = []
    for scenario in ["easy", "medium", "hard"]:
        truth_s = source_truth[source_truth["scenario"].eq(scenario)]
        pred_s = selected[selected["scenario"].eq(scenario)]
        m = method_metric_from_predictions(truth_s, pred_s)
        m.update({"method": method, "variant": variant, "scenario": scenario})
        linked = pred_s.copy()
        m["median_text_similarity"] = float(linked["text_similarity"].median()) if len(linked) else np.nan
        m["median_composite_score"] = float(linked["composite_score"].median()) if len(linked) else np.nan
        m["median_margin"] = float(linked["margin"].median()) if len(linked) else np.nan
        m["generic_cpv_share"] = float(linked["generic_cpv_flag"].mean()) if len(linked) else 0.0
        rows.append(m)
    all_m = method_metric_from_predictions(source_truth, selected)
    all_m.update({"method": method, "variant": variant, "scenario": "all"})
    linked = selected.copy()
    all_m["median_text_similarity"] = float(linked["text_similarity"].median()) if len(linked) else np.nan
    all_m["median_composite_score"] = float(linked["composite_score"].median()) if len(linked) else np.nan
    all_m["median_margin"] = float(linked["margin"].median()) if len(linked) else np.nan
    all_m["generic_cpv_share"] = float(linked["generic_cpv_flag"].mean()) if len(linked) else 0.0
    rows.append(all_m)
    for flag, label in [(True, "generic_cpv"), (False, "non_generic_cpv")]:
        source_ids = set(pairs.loc[pairs["generic_cpv_flag"].eq(flag), "source_contract_id"])
        truth_g = source_truth[source_truth["source_contract_id"].isin(source_ids)]
        pred_g = selected[selected["source_contract_id"].isin(source_ids)]
        gm = method_metric_from_predictions(truth_g, pred_g)
        gm.update({"method": method, "variant": variant, "scenario": label})
        rows.append(gm)
    return rows


def real_metrics_for_method(
    real_sources_n: int,
    real_pairs: pd.DataFrame,
    method: str,
    variant: str,
    selected: pd.DataFrame,
    score_col: str | None,
    threshold: float | None,
) -> dict:
    selected = selected.copy()
    neg_rate = np.nan
    if score_col is not None and threshold is not None:
        neg = real_pairs[real_pairs["negative_control"].fillna(False)]
        neg_rate = float(pd.to_numeric(neg[score_col], errors="coerce").ge(threshold).mean()) if len(neg) else np.nan
    manual_decided = selected[selected["manual_audit_label"].isin(["true_positive", "false_positive"])]
    manual_precision = np.nan
    if len(manual_decided):
        manual_precision = float(manual_decided["manual_audit_label"].eq("true_positive").mean())
    return {
        "method": method,
        "variant": variant,
        "event_count": int(len(selected)),
        "eligible_source_count": int(real_sources_n),
        "event_rate": float(len(selected) / real_sources_n) if real_sources_n else np.nan,
        "median_text_similarity": float(selected["text_similarity"].median()) if len(selected) else np.nan,
        "median_composite_score": float(selected["composite_score"].median()) if len(selected) else np.nan,
        "median_margin": float(selected["margin"].median()) if len(selected) else np.nan,
        "generic_cpv_share": float(selected["generic_cpv_flag"].mean()) if len(selected) else 0.0,
        "negative_control_acceptance_rate": neg_rate,
        "manual_audit_decided_n": int(len(manual_decided)),
        "manual_audit_precision": manual_precision,
        "events_available_for_survival": int(len(selected)),
    }


def threshold_grid_selection(
    source_truth: pd.DataFrame,
    synthetic_pairs: pd.DataFrame,
    real_pairs: pd.DataFrame,
    score_col: str,
    method: str,
    real_sources_n: int,
) -> tuple[pd.DataFrame, dict]:
    rows = []
    for threshold in np.round(np.arange(0.05, 0.96, 0.05), 2):
        syn_sel = predict_from_score(synthetic_pairs, score_col, threshold)
        real_sel = predict_from_score(real_pairs, score_col, threshold)
        syn_all = method_metric_from_predictions(source_truth, syn_sel)
        real_m = real_metrics_for_method(real_sources_n, real_pairs, method, "candidate", real_sel, score_col, threshold)
        rows.append(
            {
                "method": method,
                "threshold": threshold,
                "synthetic_precision": syn_all["precision"],
                "synthetic_recall": syn_all["recall"],
                "synthetic_F1": syn_all["F1"],
                "synthetic_event_rate": syn_all["event_rate"],
                "real_event_count": real_m["event_count"],
                "real_event_rate": real_m["event_rate"],
                "negative_control_acceptance_rate": real_m["negative_control_acceptance_rate"],
                "manual_audit_precision": real_m["manual_audit_precision"],
                "manual_audit_decided_n": real_m["manual_audit_decided_n"],
            }
        )
    grid = pd.DataFrame(rows)

    def choose_broad(g):
        eligible = g[(g["synthetic_precision"].ge(0.35)) & (g["real_event_count"].ge(150))]
        if eligible.empty:
            eligible = g
        return eligible.sort_values(["synthetic_recall", "real_event_count"], ascending=[False, False]).iloc[0]

    def choose_balanced(g):
        h = g.copy()
        h["event_sufficiency"] = np.minimum(h["real_event_count"] / 250.0, 1.0)
        h["audit_term"] = h["manual_audit_precision"].fillna(0.5)
        h["selection_score"] = (
            0.30 * h["synthetic_precision"]
            + 0.25 * h["synthetic_recall"]
            + 0.20 * h["event_sufficiency"]
            + 0.15 * (1.0 - h["negative_control_acceptance_rate"].fillna(1.0))
            + 0.10 * h["audit_term"]
        )
        eligible = h[h["real_event_count"].ge(80)]
        if eligible.empty:
            eligible = h
        return eligible.sort_values(["selection_score", "synthetic_precision"], ascending=[False, False]).iloc[0]

    def choose_strict(g):
        eligible = g[(g["real_event_count"].ge(25)) & (g["negative_control_acceptance_rate"].fillna(1).le(0.05))]
        if eligible.empty:
            eligible = g[g["real_event_count"].ge(25)]
        if eligible.empty:
            eligible = g
        return eligible.sort_values(["synthetic_precision", "negative_control_acceptance_rate"], ascending=[False, True]).iloc[0]

    selected = {
        "broad": choose_broad(grid),
        "balanced": choose_balanced(grid),
        "strict": choose_strict(grid),
    }
    return grid, selected


def build_active_review_sample(real_pairs: pd.DataFrame) -> pd.DataFrame:
    d = real_pairs.copy()
    d["near_m0_threshold"] = (
        d["rank"].eq(1)
        & d["text_similarity"].between(0.45, 0.55, inclusive="both")
        & d["composite_score"].between(0.45, 0.55, inclusive="both")
    )
    d["high_score_generic_cpv"] = d["rank"].eq(1) & d["generic_cpv_flag"] & d["composite_score"].ge(0.60)
    d["event0_high_nearest_candidate"] = d["rank"].eq(1) & d["composite_score"].between(0.45, 0.50, inclusive="left")
    d["low_top1_top2_margin"] = d["rank"].eq(1) & d["margin"].fillna(1.0).lt(0.05)
    d["high_text_cpv_mismatch"] = d["rank"].eq(1) & d["text_similarity"].ge(0.60) & d["cpv_score"].fillna(0).lt(0.2)
    d["same_buyer_same_cpv_weak_text"] = d["rank"].eq(1) & d["cpv_score"].fillna(0).ge(0.8) & d["text_similarity"].between(0.30, 0.50)
    criteria = [
        "near_m0_threshold",
        "high_score_generic_cpv",
        "event0_high_nearest_candidate",
        "low_top1_top2_margin",
        "high_text_cpv_mismatch",
        "same_buyer_same_cpv_weak_text",
    ]
    samples = []
    for criterion in criteria:
        part = d[d[criterion]].copy()
        if part.empty:
            continue
        part["review_reason"] = criterion
        part["priority_score"] = (
            part["composite_score"].fillna(0)
            + part["text_similarity"].fillna(0)
            + (1 - part["margin"].fillna(1)).clip(lower=0)
            + part["generic_cpv_flag"].astype(float) * 0.2
        )
        samples.append(part.sort_values("priority_score", ascending=False).head(25))
    if not samples:
        return d.head(0)
    sample = pd.concat(samples, ignore_index=True)
    sample = sample.drop_duplicates(["source_contract_id", "candidate_contract_id", "review_reason"])
    cols = [
        "review_reason",
        "priority_score",
        "source_contract_id",
        "candidate_contract_id",
        "buyer_key",
        "text_similarity",
        "cpv_score",
        "generic_cpv_flag",
        "temporal_score",
        "time_gap_months",
        "composite_score",
        "rank",
        "margin",
        "manual_audit_label",
        "m1_match_probability",
        "m2_match_probability",
        "src_objet",
        "cand_objet",
        "src_cpv",
        "cand_cpv",
        "source_start_date",
        "candidate_start_date",
    ]
    return sample[[c for c in cols if c in sample.columns]].sort_values(["review_reason", "priority_score"], ascending=[True, False])


def build_survival_dataset(base_survival: pd.DataFrame, selected: pd.DataFrame, method_label: str) -> pd.DataFrame:
    base = base_survival.copy()
    selected = selected.copy()
    selected = selected.drop_duplicates("source_contract_id", keep="first")
    selected_idx = selected.set_index("source_contract_id")
    base["event"] = 0
    base["renewal_contract_id"] = np.nan
    base["renewal_duration_months"] = np.nan
    if "censoring_duration_months" in base.columns:
        base["observed_duration_months"] = base["censoring_duration_months"].combine_first(base["observed_duration_months"])
    base["link_method"] = "none"
    for score_col in ["composite_score", "text_similarity", "cpv_match_score", "temporal_score", "score_margin"]:
        if score_col in base.columns:
            base[score_col] = np.nan
    mask = base["contract_id"].isin(selected_idx.index)
    for i in base[mask].index:
        cid = base.loc[i, "contract_id"]
        row = selected_idx.loc[cid]
        base.loc[i, "event"] = 1
        base.loc[i, "renewal_contract_id"] = row["candidate_contract_id"]
        base.loc[i, "observed_duration_months"] = row["time_gap_months"]
        base.loc[i, "renewal_duration_months"] = row["time_gap_months"]
        base.loc[i, "link_method"] = method_label
        if "composite_score" in base.columns:
            base.loc[i, "composite_score"] = row["composite_score"]
        if "text_similarity" in base.columns:
            base.loc[i, "text_similarity"] = row["text_similarity"]
        if "cpv_match_score" in base.columns:
            base.loc[i, "cpv_match_score"] = row["cpv_score"]
        if "temporal_score" in base.columns:
            base.loc[i, "temporal_score"] = row["temporal_score"]
        if "score_margin" in base.columns:
            base.loc[i, "score_margin"] = row["margin"]
    base["rule_name"] = method_label
    base["event_definition"] = f"{method_label}: proxy recurrence; identifiable reappearance of a similar procurement need, not a formally verified renewal chain"
    base["is_censored"] = 1 - base["event"].astype(int)
    return base


def survival_summary(dataset: pd.DataFrame, method: str, variant: str) -> dict:
    d = dataset.copy()
    d["observed_duration_months"] = pd.to_numeric(d["observed_duration_months"], errors="coerce")
    d["event"] = pd.to_numeric(d["event"], errors="coerce").fillna(0).astype(int)
    d = d[d["observed_duration_months"].notna() & d["observed_duration_months"].gt(0)].copy()
    km = KaplanMeierFitter()
    km.fit(d["observed_duration_months"], d["event"])
    median = km.median_survival_time_
    out = {
        "method": method,
        "variant": variant,
        "n": int(len(d)),
        "events": int(d["event"].sum()),
        "event_rate": float(d["event"].mean()) if len(d) else np.nan,
        "km_median_months": float(median) if np.isfinite(median) else np.inf,
        "km_median_reached": bool(np.isfinite(median)),
    }
    for t in [12, 24, 48, 60]:
        out[f"survival_{t}m"] = float(km.predict(t))

    cox_df = d[["observed_duration_months", "event", "declared_duration_months", "dur_was_imputed", "start_date"]].copy()
    cox_df["declared_duration_months"] = pd.to_numeric(cox_df["declared_duration_months"], errors="coerce")
    cox_df["dur_was_imputed"] = pd.to_numeric(cox_df["dur_was_imputed"], errors="coerce").fillna(0)
    cox_df["start_year"] = pd.to_datetime(cox_df["start_date"], errors="coerce").dt.year
    cox_df = cox_df.drop(columns=["start_date"]).dropna()
    cox_df = cox_df.rename(columns={"observed_duration_months": "duration"})
    out["cox_c_index"] = np.nan
    if cox_df["event"].sum() >= 10 and cox_df["event"].nunique() == 2:
        try:
            cph = CoxPHFitter(penalizer=0.05)
            cph.fit(cox_df, duration_col="duration", event_col="event")
            out["cox_c_index"] = float(cph.concordance_index_)
        except Exception:
            out["cox_c_index"] = np.nan

    aft_rows = []
    aft_df = cox_df.copy()
    for name, fitter in [
        ("WeibullAFT", WeibullAFTFitter()),
        ("LogNormalAFT", LogNormalAFTFitter()),
        ("LogLogisticAFT", LogLogisticAFTFitter()),
    ]:
        if aft_df["event"].sum() < 10:
            continue
        try:
            fitter.fit(aft_df, duration_col="duration", event_col="event")
            aft_rows.append((name, float(fitter.AIC_)))
        except Exception:
            continue
    if aft_rows:
        best_name, best_aic = sorted(aft_rows, key=lambda x: x[1])[0]
        out["best_aft_model"] = best_name
        out["best_aft_aic"] = best_aic
        out["aft_models_fit"] = "; ".join(f"{n}:{a:.2f}" for n, a in aft_rows)
    else:
        out["best_aft_model"] = np.nan
        out["best_aft_aic"] = np.nan
        out["aft_models_fit"] = ""
    return out


def save_figures(method_comparison: pd.DataFrame, survival_comparison: pd.DataFrame):
    sns.set_theme(context="paper", style="ticks")
    overall = method_comparison[method_comparison["scenario"].eq("all")].copy()
    overall["method_variant"] = overall["method"] + " " + overall["variant"]
    plt.figure(figsize=(7.2, 4.2))
    sns.scatterplot(data=overall, x="recall", y="precision", hue="method", style="variant", s=80)
    plt.title("Synthetic benchmark precision and recall")
    plt.tight_layout()
    plt.savefig(VALIDATION_FIGURES / "method_comparison_synthetic_precision_recall.png")
    plt.close()

    real = pd.read_csv(VALIDATION_TABLES / "linkage_method_comparison.csv")
    real["method_variant"] = real["method"] + " " + real["variant"]
    plt.figure(figsize=(8, 4))
    sns.barplot(data=real, x="method_variant", y="event_count", hue="method")
    plt.xticks(rotation=35, ha="right")
    plt.title("Real BOAMP proxy recurrence counts by method")
    plt.tight_layout()
    plt.savefig(VALIDATION_FIGURES / "method_comparison_real_event_counts.png")
    plt.close()

    if not survival_comparison.empty:
        surv = survival_comparison.melt(
            id_vars=["method", "variant"],
            value_vars=["survival_12m", "survival_24m", "survival_48m", "survival_60m"],
            var_name="horizon",
            value_name="survival_probability",
        )
        surv["method_variant"] = surv["method"] + " " + surv["variant"]
        plt.figure(figsize=(7.2, 4.2))
        sns.lineplot(data=surv, x="horizon", y="survival_probability", hue="method_variant", marker="o")
        plt.title("Kaplan-Meier survival probabilities by selected method")
        plt.tight_layout()
        plt.savefig(VALIDATION_FIGURES / "method_survival_km_probabilities.png")
        plt.close()


def main() -> dict:
    candidate_paths = [
        REAL_OUT / "boamp_renewal_candidates.csv",
        VALIDATION_TABLES / "calibrated_real_best_links_all_rules.csv",
        VALIDATION_TABLES / "calibrated_real_best_links_balanced.csv",
        VALIDATION_TABLES / "calibrated_real_best_links_broad.csv",
        VALIDATION_TABLES / "calibrated_real_best_links_strict.csv",
        SYNTHETIC / "synthetic_boamp_true_links_all.csv",
        VALIDATION_TABLES / "synthetic_threshold_grid.csv",
        EVENT_VALIDATION / "manual_validation_audit_labeled.csv",
        PROCESSED / "boamp_phase2_survival_calibrated_balanced.csv",
        SURVIVAL_TABLES / "calibrated_rule_km_summary.csv",
        SURVIVAL_TABLES / "calibrated_rule_cox_comparison.csv",
        SURVIVAL_TABLES / "calibrated_balanced_aft_comparison.csv",
    ]
    input_inventory = pd.DataFrame(
        [
            {
                "file_path": rel(p),
                "exists": p.exists(),
                "modified_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds") if p.exists() else np.nan,
                "rows": len(pd.read_csv(p, low_memory=False)) if p.exists() and p.suffix == ".csv" else np.nan,
            }
            for p in candidate_paths
        ]
    )
    input_inventory.to_csv(VALIDATION_TABLES / "method_comparison_input_inventory.csv", index=False)

    real_candidates = load_csv(REAL_OUT / "boamp_renewal_candidates.csv")
    real_links = load_csv(REAL_OUT / "boamp_renewal_links.csv")
    notices = load_csv(SYNTHETIC / "synthetic_boamp_notices_all.csv")
    truth = load_csv(SYNTHETIC / "synthetic_boamp_true_links_all.csv")
    rules = load_csv(VALIDATION_TABLES / "recommended_event_rules.csv")
    synthetic_threshold_grid = load_csv(VALIDATION_TABLES / "synthetic_threshold_grid.csv")
    manual = load_csv(EVENT_VALIDATION / "manual_validation_audit_labeled.csv") if (EVENT_VALIDATION / "manual_validation_audit_labeled.csv").exists() else pd.DataFrame()

    real_pairs = make_real_pairs(real_candidates, manual)
    synthetic_pairs = make_synthetic_pairs(notices, truth)
    synthetic_pairs, real_pairs, model_notes = add_probabilities(synthetic_pairs, real_pairs)

    unified_cols = [
        "candidate_pair_dataset",
        "scenario",
        "source_contract_id",
        "candidate_contract_id",
        "buyer_key",
        "text_similarity",
        "cpv_score",
        "generic_cpv_flag",
        "temporal_score",
        "time_gap_months",
        "composite_score",
        "rank",
        "margin",
        "buyer_frequency",
        "missing_cpv_flag",
        "missing_duration_flag",
        "synthetic_true_match",
        "negative_control",
        "manual_audit_label",
        "m1_match_probability",
        "m2_match_probability",
    ]
    unified = pd.concat([real_pairs, synthetic_pairs], ignore_index=True, sort=False)
    unified[[c for c in unified_cols if c in unified.columns]].to_csv(
        VALIDATION_TABLES / "unified_candidate_pair_table.csv", index=False
    )

    source_truth = truth.rename(columns={"source_id": "source_contract_id", "true_candidate_id": "true_candidate_id"})
    source_truth["true_event"] = source_truth["true_event"].astype(int)

    selected_sets: dict[tuple[str, str], pd.DataFrame] = {}
    synthetic_metric_rows = []
    real_metric_rows = []
    threshold_rows = []
    threshold_selection_rows = []
    real_sources_n = len(real_links)

    for _, row in rules.iterrows():
        variant = str(row["rule_name"])
        calibrated_path = VALIDATION_TABLES / f"calibrated_real_best_links_{variant}.csv"
        calibrated_selected = make_calibrated_selected(load_csv(calibrated_path), real_pairs, variant)
        syn_sel = select_by_rule(synthetic_pairs, row["text_threshold"], row["composite_threshold"], row["margin_threshold"])
        selected_sets[("M0", variant)] = calibrated_selected
        grid_match = synthetic_threshold_grid[
            synthetic_threshold_grid["text_threshold"].astype(float).eq(float(row["text_threshold"]))
            & synthetic_threshold_grid["W"].astype(int).eq(int(row["W"]))
            & synthetic_threshold_grid["generic_cpv_rule"].astype(str).eq(str(row["generic_cpv_rule"]))
            & synthetic_threshold_grid["composite_threshold"].astype(str).str.lower().eq(str(row["composite_threshold"]).lower())
            & synthetic_threshold_grid["margin_threshold"].astype(str).str.lower().eq(str(row["margin_threshold"]).lower())
        ].copy()
        if not grid_match.empty:
            for _, gm in grid_match.iterrows():
                synthetic_metric_rows.append(
                    {
                        "method": "M0",
                        "variant": variant,
                        "scenario": gm["scenario"],
                        "TP": int(gm["TP"]),
                        "FP": int(gm["FP"]),
                        "FN": int(gm["FN"]),
                        "TN": int(gm["TN"]),
                        "precision": float(gm["precision"]),
                        "recall": float(gm["recall"]),
                        "F1": float(gm["F1"]),
                        "event_count": int(gm["event_count"]),
                        "event_rate": float(gm["linking_rate"]),
                        "median_text_similarity": float(gm["median_text_similarity"]),
                        "median_composite_score": float(gm["median_composite_score"]),
                        "median_margin": float(gm["median_margin"]) if not pd.isna(gm["median_margin"]) else np.nan,
                        "generic_cpv_share": float(gm["share_generic_cpv_links"]),
                    }
                )
            agg = grid_match[["TP", "FP", "FN", "TN", "event_count", "eligible_source_count"]].sum(numeric_only=True)
            precision = agg["TP"] / (agg["TP"] + agg["FP"]) if (agg["TP"] + agg["FP"]) else 0.0
            recall = agg["TP"] / (agg["TP"] + agg["FN"]) if (agg["TP"] + agg["FN"]) else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            synthetic_metric_rows.append(
                {
                    "method": "M0",
                    "variant": variant,
                    "scenario": "all",
                    "TP": int(agg["TP"]),
                    "FP": int(agg["FP"]),
                    "FN": int(agg["FN"]),
                    "TN": int(agg["TN"]),
                    "precision": float(precision),
                    "recall": float(recall),
                    "F1": float(f1),
                    "event_count": int(agg["event_count"]),
                    "event_rate": float(agg["event_count"] / agg["eligible_source_count"]),
                    "median_text_similarity": np.nan,
                    "median_composite_score": np.nan,
                    "median_margin": np.nan,
                    "generic_cpv_share": float(grid_match["share_generic_cpv_links"].mean()),
                }
            )
            synthetic_metric_rows.extend(
                [
                    r
                    for r in synthetic_metrics_for_method(source_truth, synthetic_pairs, "M0", variant, syn_sel)
                    if r["scenario"] in {"generic_cpv", "non_generic_cpv"}
                ]
            )
        else:
            synthetic_metric_rows.extend(synthetic_metrics_for_method(source_truth, synthetic_pairs, "M0", variant, syn_sel))
        m0_real = real_metrics_for_method(real_sources_n, real_pairs, "M0", variant, calibrated_selected, None, None)
        m0_rule = row.to_dict()
        m0_real["negative_control_acceptance_rate"] = float(m0_rule.get("negative_control_pass_rate", np.nan))
        m0_real["events_available_for_survival"] = int(m0_rule.get("events_available_for_survival", len(calibrated_selected)))
        real_metric_rows.append(m0_real)
        threshold_selection_rows.append(
            {
                "method": "M0",
                "variant": variant,
                "selection_score": np.nan,
                "threshold": row["composite_threshold"],
                "text_threshold": row["text_threshold"],
                "composite_threshold": row["composite_threshold"],
                "margin_threshold": row["margin_threshold"],
                "W": row["W"],
                "generic_cpv_rule": row["generic_cpv_rule"],
                "selection_basis": "Current calibrated reference rule M0 from recommended_event_rules.csv.",
            }
        )

    for method, score_col in [("M1", "m1_match_probability"), ("M2", "m2_match_probability")]:
        grid, selected_thresholds = threshold_grid_selection(source_truth, synthetic_pairs, real_pairs, score_col, method, real_sources_n)
        threshold_rows.append(grid)
        for variant, selected in selected_thresholds.items():
            threshold = float(selected["threshold"])
            syn_sel = predict_from_score(synthetic_pairs, score_col, threshold)
            real_sel = predict_from_score(real_pairs, score_col, threshold)
            selected_sets[(method, variant)] = real_sel
            synthetic_metric_rows.extend(synthetic_metrics_for_method(source_truth, synthetic_pairs, method, variant, syn_sel))
            real_metric_rows.append(real_metrics_for_method(real_sources_n, real_pairs, method, variant, real_sel, score_col, threshold))
            threshold_selection_rows.append(
                {
                    "method": method,
                    "variant": variant,
                    "selection_score": selected.get("selection_score", np.nan),
                    "threshold": threshold,
                    "text_threshold": np.nan,
                    "composite_threshold": np.nan,
                    "margin_threshold": np.nan,
                    "W": 6,
                    "generic_cpv_rule": "corrected_generic_cpv_features",
                    "selection_basis": "Selected from observed probability-threshold grid using synthetic precision/recall, negative controls, real BOAMP event count, manual audit labels when available, and survival event sufficiency.",
                }
            )

    synthetic_comparison = pd.DataFrame(synthetic_metric_rows)
    synthetic_comparison.to_csv(VALIDATION_TABLES / "linkage_method_comparison_synthetic_metrics.csv", index=False)

    real_comparison = pd.DataFrame(real_metric_rows)
    real_comparison = real_comparison.sort_values(["method", "variant"])
    real_comparison.to_csv(VALIDATION_TABLES / "linkage_method_comparison.csv", index=False)

    threshold_results = pd.concat(threshold_rows, ignore_index=True)
    threshold_results.to_csv(VALIDATION_TABLES / "probabilistic_threshold_grid.csv", index=False)
    threshold_selection = pd.DataFrame(threshold_selection_rows)
    threshold_selection.to_csv(VALIDATION_TABLES / "probabilistic_linkage_results.csv", index=False)

    active_sample = build_active_review_sample(real_pairs)
    active_sample.to_csv(VALIDATION_TABLES / "active_learning_review_sample.csv", index=False)

    balanced = real_comparison[real_comparison["variant"].eq("balanced")].copy()
    syn_all = synthetic_comparison[synthetic_comparison["scenario"].eq("all")][["method", "variant", "precision", "recall", "F1"]]
    balanced = balanced.merge(syn_all, on=["method", "variant"], how="left", suffixes=("", "_synthetic"))
    balanced["manual_term"] = balanced["manual_audit_precision"].fillna(0.5)
    balanced["selection_score"] = (
        0.30 * balanced["precision"]
        + 0.20 * balanced["recall"]
        + 0.20 * np.minimum(balanced["event_count"] / 250.0, 1.0)
        + 0.20 * (1 - balanced["negative_control_acceptance_rate"].fillna(1.0))
        + 0.10 * balanced["manual_term"]
    )
    m0_score = float(balanced.loc[balanced["method"].eq("M0"), "selection_score"].iloc[0])
    best_row = balanced.sort_values("selection_score", ascending=False).iloc[0]
    selected_method = "M0"
    if best_row["method"] != "M0" and best_row["selection_score"] > m0_score + 0.05:
        recommendation = "retain_m0_balanced_as_current_main_method_pending_targeted_review_of_best_alternative"
    else:
        recommendation = "retain_m0_balanced_as_main_method"

    best_alt = balanced[balanced["method"].ne("M0")].sort_values("selection_score", ascending=False).iloc[0]
    final_recommendation = pd.DataFrame(
        [
            {
                "selected_method": selected_method,
                "selected_variant": "balanced",
                "recommendation": recommendation,
                "reference_method": "M0 calibrated balanced composite rule",
                "best_alternative_method": best_alt["method"],
                "best_alternative_variant": "balanced",
                "m0_balanced_score": m0_score,
                "best_observed_score": float(best_row["selection_score"]),
                "language_note": "Real BOAMP event labels remain proxy recurrences: identifiable reappearances of similar procurement needs, not formally verified renewal chains. Real precision and recall are not directly observable.",
            }
        ]
    )
    final_recommendation.to_csv(VALIDATION_TABLES / "final_method_recommendation.csv", index=False)

    base_survival = load_csv(PROCESSED / "boamp_phase2_survival_calibrated_balanced.csv")
    survival_targets = [("M0", "balanced"), (str(best_alt["method"]), "balanced"), ("M0", "strict")]
    survival_rows = []
    for method, variant in survival_targets:
        label = f"{method}_{variant}"
        selected = selected_sets[(method, variant)]
        surv = build_survival_dataset(base_survival, selected, label)
        surv_path = PROCESSED / f"boamp_phase2_survival_method_{method.lower()}_{variant}.csv"
        surv.to_csv(surv_path, index=False)
        row = survival_summary(surv, method, variant)
        row["survival_dataset"] = rel(surv_path)
        if method == "M0" and variant == "balanced" and (SURVIVAL_TABLES / "renewal_risk_12_24_months_calibrated_balanced.csv").exists():
            risk = load_csv(SURVIVAL_TABLES / "renewal_risk_12_24_months_calibrated_balanced.csv")
            row["operational_risk_indicators_available"] = True
            row["risk_indicator_rows"] = int(len(risk))
            row["median_p_renewal_12m"] = float(pd.to_numeric(risk["p_renewal_12m"], errors="coerce").median())
            row["median_p_renewal_24m"] = float(pd.to_numeric(risk["p_renewal_24m"], errors="coerce").median())
        else:
            row["operational_risk_indicators_available"] = False
            row["risk_indicator_rows"] = 0
            row["median_p_renewal_12m"] = np.nan
            row["median_p_renewal_24m"] = np.nan
        survival_rows.append(row)

    survival_comparison = pd.DataFrame(survival_rows)
    survival_comparison.to_csv(VALIDATION_TABLES / "method_survival_comparison.csv", index=False)
    save_figures(synthetic_comparison, survival_comparison)

    summary = {
        "completed_successfully": True,
        "files_loaded": input_inventory[input_inventory["exists"]]["file_path"].tolist(),
        "files_created": [
            "reports/tables/validation/unified_candidate_pair_table.csv",
            "reports/tables/validation/linkage_method_comparison.csv",
            "reports/tables/validation/linkage_method_comparison_synthetic_metrics.csv",
            "reports/tables/validation/active_learning_review_sample.csv",
            "reports/tables/validation/probabilistic_linkage_results.csv",
            "reports/tables/validation/final_method_recommendation.csv",
            "reports/tables/validation/method_survival_comparison.csv",
            "reports/figures/validation/method_comparison_synthetic_precision_recall.png",
            "reports/figures/validation/method_comparison_real_event_counts.png",
            "reports/figures/validation/method_survival_km_probabilities.png",
        ],
        "methods_tested": {
            "M0": "Current calibrated composite rule reference.",
            "M1": model_notes["m1_model"],
            "M2": model_notes["m2_model"],
        },
        "selected_method": selected_method,
        "recommendation": recommendation,
        "selected_thresholds": threshold_selection.to_dict(orient="records"),
        "real_boamp_event_counts": real_comparison[["method", "variant", "event_count", "event_rate"]].to_dict(orient="records"),
        "synthetic_benchmark_metrics_all": synthetic_comparison[synthetic_comparison["scenario"].eq("all")][
            ["method", "variant", "precision", "recall", "FP", "FN", "event_rate"]
        ].to_dict(orient="records"),
        "survival_results": survival_comparison.to_dict(orient="records"),
        "manual_training_pairs": model_notes["manual_training_pairs"],
        "language_guardrail": "No real BOAMP precision/recall is claimed; event means proxy recurrence.",
    }
    (VALIDATION_TABLES / "method_comparison_execution_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n=== BOAMP method-comparison execution summary ===")
    print(f"Files loaded: {len(summary['files_loaded'])}")
    for path in summary["files_loaded"]:
        print(f"  - {path}")
    print(f"Files created: {len(summary['files_created'])}")
    for path in summary["files_created"]:
        print(f"  - {path}")
    print("Methods tested: M0, M1, M2")
    print(f"Selected method: {selected_method} ({recommendation})")
    print("Selected thresholds:")
    for row in summary["selected_thresholds"]:
        print(f"  - {row['method']} {row['variant']}: threshold={row['threshold']}, text={row['text_threshold']}, composite={row['composite_threshold']}")
    print("Real BOAMP event counts:")
    for row in summary["real_boamp_event_counts"]:
        print(f"  - {row['method']} {row['variant']}: {row['event_count']} ({row['event_rate']:.1%})")
    print("Synthetic benchmark metrics (all scenarios):")
    for row in summary["synthetic_benchmark_metrics_all"]:
        print(f"  - {row['method']} {row['variant']}: precision={row['precision']:.3f}, recall={row['recall']:.3f}, FP={row['FP']}, FN={row['FN']}")
    print("Survival results:")
    for row in summary["survival_results"]:
        print(
            f"  - {row['method']} {row['variant']}: events={row['events']}, "
            f"S12={row['survival_12m']:.3f}, S24={row['survival_24m']:.3f}, "
            f"KM median reached={row['km_median_reached']}, Cox C-index={row['cox_c_index']}"
        )
    print("Pipeline completed successfully: True")
    return summary


if __name__ == "__main__":
    main()
