from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from current_boamp_lib import (
    FIGURES_LINKAGE,
    PROCESSED_CURRENT,
    TABLES_LINKAGE,
    append_run_log,
    cpv_score,
    ensure_dirs,
    is_generic_cpv,
    month_diff,
    temporal_score,
    utc_now,
)
from src.visualization.academic_style import apply_academic_style, save_pdf_png

MIN_GAP_MONTHS = 1.0
EARLY_TOLERANCE_MONTHS = 12.0
LATE_TOLERANCE_MONTHS = 24.0
TEMPORAL_WINDOW_FOR_SCORE = 12.0


def text_similarity_matrix(texts: list[str]) -> tuple[np.ndarray, str]:
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        emb = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
        return np.asarray(emb) @ np.asarray(emb).T, "sentence_transformers:paraphrase-multilingual-MiniLM-L12-v2"
    except Exception as exc:
        print(f"WARNING: sentence-transformer unavailable ({exc}); using char 3-gram TF-IDF fallback")
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
        mat = vec.fit_transform(texts)
        return cosine_similarity(mat), "tfidf_char_3_5_fallback"


def main() -> None:
    ensure_dirs()
    pop_path = PROCESSED_CURRENT / "boamp_survival_population_base.csv"
    if not pop_path.exists():
        raise SystemExit(f"Missing {pop_path}; run build_current_survival_population.py first.")
    pop = pd.read_csv(pop_path, parse_dates=["source_date", "estimated_end_date", "censoring_date"], low_memory=False)
    eligible = pop[pop["eligible_for_linkage"].astype(str).str.lower().isin(["true", "1", "yes"])].copy()
    eligible = eligible.sort_values("source_date").reset_index(drop=True)
    texts = eligible["objet_clean"].fillna("").astype(str).tolist()
    sim, backend = text_similarity_matrix(texts)

    rows = []
    for buyer_key, grp in eligible.groupby("buyer_key", sort=False):
        idxs = grp.index.to_list()
        if len(idxs) <= 1:
            continue
        for src_idx in idxs:
            src = eligible.loc[src_idx]
            exp = float(src["declared_duration_months"])
            low = max(MIN_GAP_MONTHS, exp - EARLY_TOLERANCE_MONTHS)
            high = exp + LATE_TOLERANCE_MONTHS
            for cand_idx in idxs:
                if cand_idx == src_idx:
                    continue
                cand = eligible.loc[cand_idx]
                if cand["source_date"] <= src["source_date"]:
                    continue
                gap = month_diff(src["source_date"], cand["source_date"])
                if gap < low or gap > high:
                    continue
                tscore = float(sim[src_idx, cand_idx])
                cscore = cpv_score(src["cpv_clean"], cand["cpv_clean"])
                temps = temporal_score(gap, exp, TEMPORAL_WINDOW_FOR_SCORE)
                buyer_quality = 1.0 if src["buyer_key_type"] != "NAME" else 0.72
                if pd.isna(cscore):
                    composite = (0.45 * tscore + 0.25 * temps + 0.15 * buyer_quality) / 0.85
                else:
                    composite = 0.42 * tscore + 0.23 * cscore + 0.20 * temps + 0.15 * buyer_quality
                rows.append(
                    {
                        "source_contract_id": src["contract_id"],
                        "candidate_contract_id": cand["contract_id"],
                        "src_idweb": src["idweb"],
                        "cand_idweb": cand["idweb"],
                        "buyer_key": buyer_key,
                        "buyer_key_type": src["buyer_key_type"],
                        "src_buyer_name": src["buyer_name_raw"],
                        "src_source_date": src["source_date"],
                        "cand_source_date": cand["source_date"],
                        "src_estimated_end_date": src["estimated_end_date"],
                        "gap_months": round(gap, 2),
                        "src_duration_months": exp,
                        "src_cpv": src["cpv_clean"],
                        "cand_cpv": cand["cpv_clean"],
                        "src_segment": src["segment"],
                        "cand_segment": cand["segment"],
                        "text_similarity": round(tscore, 5),
                        "cpv_score": cscore,
                        "temporal_score": round(float(temps), 5),
                        "buyer_quality_score": buyer_quality,
                        "composite_score": round(float(composite), 5),
                        "source_generic_cpv": is_generic_cpv(src["cpv_clean"]),
                        "candidate_generic_cpv": is_generic_cpv(cand["cpv_clean"]),
                        "missing_cpv_flag": pd.isna(src["cpv_clean"]) or pd.isna(cand["cpv_clean"]),
                        "duration_imputed_flag": bool(src["duration_imputed_flag"]),
                    }
                )

    pairs = pd.DataFrame(rows)
    if not pairs.empty:
        pairs = pairs.sort_values(["source_contract_id", "composite_score", "text_similarity"], ascending=[True, False, False])
        pairs["candidate_rank"] = pairs.groupby("source_contract_id").cumcount() + 1
        top2 = pairs[pairs["candidate_rank"].le(2)].pivot(index="source_contract_id", columns="candidate_rank", values="composite_score")
        margin = (top2.get(1) - top2.get(2)).rename("score_margin")
        pairs = pairs.merge(margin, on="source_contract_id", how="left")
        pairs["score_margin"] = np.where(pairs["candidate_rank"].eq(1), pairs["score_margin"], np.nan)
        pairs["candidate_pair_text_backend"] = backend
    out_path = PROCESSED_CURRENT / "boamp_candidate_pairs_enriched.csv"
    pairs.to_csv(out_path, index=False)

    summary = pd.DataFrame(
        [
            {"metric": "eligible_sources", "value": len(eligible)},
            {"metric": "candidate_pairs", "value": len(pairs)},
            {"metric": "sources_with_candidate", "value": pairs["source_contract_id"].nunique() if not pairs.empty else 0},
            {"metric": "text_similarity_backend", "value": backend},
            {"metric": "candidate_time_window", "value": f"duration-{EARLY_TOLERANCE_MONTHS:g} to duration+{LATE_TOLERANCE_MONTHS:g} months"},
        ]
    )
    summary.to_csv(TABLES_LINKAGE / "candidate_generation_summary.csv", index=False)
    if not pairs.empty:
        pairs.assign(year=pd.to_datetime(pairs["src_source_date"]).dt.year).groupby("year").agg(
            candidate_pairs=("source_contract_id", "count"),
            sources_with_candidate=("source_contract_id", "nunique"),
        ).reset_index().to_csv(TABLES_LINKAGE / "candidate_pairs_by_year.csv", index=False)
    else:
        pd.DataFrame(columns=["year", "candidate_pairs", "sources_with_candidate"]).to_csv(TABLES_LINKAGE / "candidate_pairs_by_year.csv", index=False)

    apply_academic_style()
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    counts = pairs.groupby("source_contract_id").size() if not pairs.empty else pd.Series(dtype=int)
    ax.hist(counts, bins=30, color="#4C78A8", edgecolor="white")
    ax.set_title("Current Candidate Count Distribution")
    ax.set_xlabel("Candidate pairs per source contract")
    ax.set_ylabel("Source contracts")
    save_pdf_png(fig, FIGURES_LINKAGE / "candidate_count_distribution")
    plt.close(fig)

    append_run_log(
        [
            "",
            f"## Current candidate generation - {utc_now()}",
            f"- Eligible sources: {len(eligible)}",
            f"- Candidate pairs: {len(pairs)}",
            f"- Text backend: {backend}",
            f"- Output: {out_path}",
        ]
    )
    print("=== Current candidate generation ===")
    print(summary.to_string(index=False))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
