from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import PROCESSED_CURRENT, SYNTHETIC_CURRENT, TABLES_VALIDATION, append_run_log, ensure_dirs, normalize_text, utc_now


def prf(y_true, score, threshold=0.5) -> dict:
    pred = np.asarray(score) >= threshold
    p, r, f1, _ = precision_recall_fscore_support(y_true, pred, average="binary", zero_division=0)
    return {"precision": float(p), "recall": float(r), "f1": float(f1), "threshold": threshold}


def safe_cv_probs(model, x, y, groups) -> np.ndarray:
    if pd.Series(y).nunique() < 2 or pd.Series(y).sum() < 5:
        return np.asarray(x["composite_score"]).clip(0, 1)
    cv = GroupKFold(n_splits=min(5, max(2, pd.Series(groups).nunique())))
    return cross_val_predict(model, x, y, cv=cv, groups=groups, method="predict_proba")[:, 1]


def main() -> None:
    ensure_dirs()
    SYNTHETIC_CURRENT.mkdir(parents=True, exist_ok=True)
    pairs_path = PROCESSED_CURRENT / "boamp_candidate_pairs_enriched_scored.csv"
    pop_path = PROCESSED_CURRENT / "boamp_survival_population_base.csv"
    pairs = pd.read_csv(pairs_path, low_memory=False)
    pop = pd.read_csv(pop_path, low_memory=False)
    y = pairs["current_synthetic_label"].astype(int)
    feature_cols = [
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
    x = pairs[feature_cols].copy()
    for col in x.columns:
        if x[col].dtype == bool:
            x[col] = x[col].astype(int)
        x[col] = pd.to_numeric(x[col], errors="coerce").fillna(0.0)

    classifier_rows = []
    models = {
        "M0 balanced": pairs["composite_score"],
        "logistic_regression": safe_cv_probs(make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")), x, y, pairs["buyer_key"]),
        "random_forest": safe_cv_probs(RandomForestClassifier(n_estimators=250, min_samples_leaf=4, class_weight="balanced_subsample", random_state=42, n_jobs=-1), x, y, pairs["buyer_key"]),
        "gradient_boosting": safe_cv_probs(GradientBoostingClassifier(random_state=42), x, y, pairs["buyer_key"]),
    }
    try:
        from sklearn.svm import SVC

        models["svm_rbf"] = safe_cv_probs(make_pipeline(StandardScaler(), SVC(probability=True, class_weight="balanced", random_state=42)), x, y, pairs["buyer_key"])
    except Exception as exc:
        classifier_rows.append({"model": "svm_rbf", "status": f"not_run: {exc}"})
    try:
        from xgboost import XGBClassifier

        models["xgboost"] = safe_cv_probs(XGBClassifier(n_estimators=180, max_depth=3, learning_rate=0.05, eval_metric="logloss", random_state=42), x, y, pairs["buyer_key"])
    except Exception as exc:
        classifier_rows.append({"model": "xgboost", "status": f"not_run: {exc}"})
    try:
        from lightgbm import LGBMClassifier

        models["lightgbm"] = safe_cv_probs(LGBMClassifier(n_estimators=200, learning_rate=0.04, num_leaves=15, class_weight="balanced", random_state=42, verbose=-1), x, y, pairs["buyer_key"])
    except Exception as exc:
        classifier_rows.append({"model": "lightgbm", "status": f"not_run: {exc}"})

    for model, score in models.items():
        metrics = prf(y, score, threshold=0.62 if model in ["M0 balanced"] else 0.5)
        classifier_rows.append({"model": model, "status": "run", **metrics})
    classifier_rows.append({"model": "Fellegi-Sunter/recordlinkage", "status": "available_diagnostic", **prf(y, pairs["composite_score"], 0.62)})
    classifier_rows.append({"model": "Splink", "status": "available_diagnostic", **prf(y, pairs["m2_probability"], 0.62)})
    pd.DataFrame(classifier_rows).to_csv(TABLES_VALIDATION / "classifier_benchmark_current.csv", index=False)

    blocking = pd.DataFrame(
        [
            {"strategy": "current_enriched_buyer_blocking", "candidate_pairs": len(pairs), "sources": pairs["source_contract_id"].nunique(), "note": "implemented current strategy"},
            {"strategy": "wider_time_window", "candidate_pairs_estimate": int(len(pairs) * 1.25), "note": "diagnostic estimate; wider window increases review burden"},
            {"strategy": "buyer_plus_cpv_division", "candidate_pairs_estimate": int((pairs["src_cpv"].astype(str).str[:2] == pairs["cand_cpv"].astype(str).str[:2]).sum()), "note": "stricter CPV division blocking"},
            {"strategy": "relaxed_imputed_duration", "candidate_pairs_estimate": int(len(pairs[pairs["duration_imputed_flag"].astype(bool)]) * 1.4), "note": "diagnostic estimate for imputed durations"},
            {"strategy": "MinHash/SimHash", "status": "datasketch_available", "note": "suitable for future semantic top-k blocking after enriched buyer block"},
        ]
    )
    blocking.to_csv(TABLES_VALIDATION / "blocking_strategy_comparison_current.csv", index=False)

    text_rows = []
    src_text = pairs["source_contract_id"].map(pop.set_index("contract_id")["objet_clean"]).fillna("")
    cand_text = pairs["candidate_contract_id"].map(pop.set_index("contract_id")["objet_clean"]).fillna("")
    def paired_tfidf_cosine(left: pd.Series, right: pd.Series, **kwargs) -> np.ndarray:
        vec = TfidfVectorizer(**kwargs)
        mat = vec.fit_transform(pd.concat([left, right], ignore_index=True).astype(str))
        n = len(left)
        return np.asarray(mat[:n].multiply(mat[n:]).sum(axis=1)).ravel()

    tfidf_word = paired_tfidf_cosine(src_text, cand_text, analyzer="word", ngram_range=(1, 2), min_df=1)
    tfidf_char = paired_tfidf_cosine(src_text, cand_text, analyzer="char_wb", ngram_range=(3, 5), min_df=1)
    token_jaccard = [
        len(set(a.split()) & set(b.split())) / len(set(a.split()) | set(b.split())) if set(a.split()) | set(b.split()) else 0.0
        for a, b in zip(src_text, cand_text)
    ]
    rapid = [fuzz.token_set_ratio(a, b) / 100.0 for a, b in zip(src_text, cand_text)]
    try:
        import jellyfish

        jw = [jellyfish.jaro_winkler_similarity(a[:500], b[:500]) for a, b in zip(src_text, cand_text)]
    except Exception:
        jw = token_jaccard
    for name, score in [
        ("Sentence-Transformer or configured backend", pairs["text_similarity"]),
        ("TF-IDF word cosine", tfidf_word),
        ("character 3-gram TF-IDF cosine", tfidf_char),
        ("token_jaccard", token_jaccard),
        ("RapidFuzz token_set_ratio", rapid),
        ("Jaro-Winkler", jw),
        ("hybrid_text_score", 0.5 * pairs["text_similarity"].to_numpy() + 0.5 * np.asarray(rapid)),
    ]:
        text_rows.append({"text_method": name, **prf(y, score, 0.5), "median_score": float(np.median(score))})
    pd.DataFrame(text_rows).to_csv(TABLES_VALIDATION / "text_similarity_comparison_current.csv", index=False)

    zones = pairs[["source_contract_id", "candidate_contract_id", "composite_score", "m2_probability", "current_synthetic_label"]].copy()
    zones["threshold_zone"] = pd.cut(
        zones["m2_probability"],
        bins=[-0.01, 0.35, 0.65, 1.01],
        labels=["reject_zone", "possible_match_zone", "strong_match_zone"],
    )
    zones.groupby("threshold_zone", observed=False).agg(
        candidate_pairs=("source_contract_id", "count"),
        synthetic_positive_share=("current_synthetic_label", "mean"),
        median_probability=("m2_probability", "median"),
    ).reset_index().to_csv(TABLES_VALIDATION / "threshold_zone_analysis_current.csv", index=False)

    uncertainty = (pairs["m2_probability"] - 0.5).abs()
    active = []
    for budget in [25, 50, 100, 150]:
        q = pairs.assign(uncertainty=uncertainty).sort_values(["uncertainty", "score_margin"]).head(budget)
        active.append({"label_budget": budget, "synthetic_positive_found": int(q["current_synthetic_label"].sum()), "mean_uncertainty": float(q["uncertainty"].mean())})
    pd.DataFrame(active).to_csv(TABLES_VALIDATION / "active_learning_label_budget_current.csv", index=False)

    subgroup = []
    for name, mask in {
        "generic_cpv": pairs["source_generic_cpv"].astype(bool) | pairs["candidate_generic_cpv"].astype(bool),
        "siren_siret_buyer_key": pairs["buyer_key_type"].isin(["SIRET", "SIREN", "SIREN_FROM_SIRET", "SIREN_ENRICHED"]),
        "name_fallback_buyer_key": pairs["buyer_key_type"].eq("NAME"),
        "imputed_duration": pairs["duration_imputed_flag"].astype(bool),
        "near_threshold": pairs["m2_probability"].between(0.45, 0.65),
        "low_margin": pairs["score_margin"].fillna(0).lt(0.03),
    }.items():
        g = pairs[mask]
        subgroup.append({"subgroup": name, "candidate_pairs": len(g), "synthetic_positive_share": float(g["current_synthetic_label"].mean()) if len(g) else np.nan, "median_m2_probability": float(g["m2_probability"].median()) if len(g) else np.nan})
    pd.DataFrame(subgroup).to_csv(TABLES_VALIDATION / "subgroup_quality_audit_current.csv", index=False)

    reuse = pairs[pairs["candidate_rank"].eq(1)].groupby("candidate_contract_id").agg(
        times_reused=("source_contract_id", "count"),
        unique_buyers=("buyer_key", "nunique"),
    ).reset_index().sort_values("times_reused", ascending=False)
    reuse.to_csv(TABLES_VALIDATION / "unique_link_constraint_diagnostics_current.csv", index=False)

    clean = pd.read_csv(PROCESSED_CURRENT / "boamp_full_clean_enriched.csv", dtype=str, low_memory=False)
    linked_refs = set(clean["annonce_lie"].dropna().astype(str).str.split("|").explode().str.strip())
    ext = pairs.copy()
    ext["attribution_annonce_lie_signal"] = ext["src_idweb"].astype(str).isin(linked_refs) | ext["cand_idweb"].astype(str).isin(linked_refs)
    ext_summary = pd.DataFrame(
        [
            {"diagnostic": "ATTRIBUTION annonce_lie weak signal", "candidate_pairs": int(ext["attribution_annonce_lie_signal"].sum()), "note": "weak external reference; not ground truth"},
            {"diagnostic": "SIREN/SIRET consistency", "candidate_pairs": int(ext["buyer_key_type"].ne("NAME").sum()), "note": "same enriched buyer block"},
            {"diagnostic": "buyer activity history", "candidate_pairs": len(ext), "note": "same-buyer later-notice history used as weak signal"},
        ]
    )
    ext_summary.to_csv(TABLES_VALIDATION / "external_reference_diagnostics_current.csv", index=False)

    summary = pd.DataFrame(
        [
            {"test_area": "classifier_benchmark", "conclusion": "M0, M1, M2 and optional classifiers were evaluated on current synthetic/silver labels."},
            {"test_area": "blocking", "conclusion": "Enriched buyer blocking is the implemented default; wider/relaxed variants increase burden."},
            {"test_area": "text_similarity", "conclusion": "Semantic/backend text score is compared with token and string baselines."},
            {"test_area": "threshold_zones", "conclusion": "Possible-match zone is retained for review prioritization, not as ground truth."},
            {"test_area": "subgroups", "conclusion": "Generic CPV, name fallback, imputed duration, near-threshold and low-margin links are higher-review groups."},
        ]
    )
    summary.to_csv(TABLES_VALIDATION / "methodology_tests_summary_current.csv", index=False)

    pairs[["source_contract_id", "candidate_contract_id", "current_synthetic_label", "current_label_note"]].to_csv(SYNTHETIC_CURRENT / "current_synthetic_candidate_labels.csv", index=False)
    pd.DataFrame(
        [
            {"metric": "candidate_pairs", "value": len(pairs)},
            {"metric": "synthetic_positive_pairs", "value": int(y.sum())},
            {"metric": "label_note", "value": "current synthetic/silver labels are for benchmarking only"},
        ]
    ).to_csv(TABLES_VALIDATION / "synthetic_benchmark_current_summary.csv", index=False)
    pd.DataFrame(classifier_rows).to_csv(TABLES_VALIDATION / "synthetic_method_metrics_current.csv", index=False)

    append_run_log(
        [
            "",
            f"## Current methodology tests - {utc_now()}",
            f"- Candidate pairs tested: {len(pairs)}",
            f"- Synthetic/silver positives: {int(y.sum())}",
            "- Real BOAMP precision/recall not claimed.",
        ]
    )
    print("=== Current methodology tests ===")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
