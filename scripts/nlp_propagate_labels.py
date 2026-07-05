"""
Phase 2 NLP — Step 3: Full Corpus Propagation

Loads the best trained model (SBERT if it won, else TF-IDF baseline),
applies it to all 3,181 rows of boamp_full_clean.csv, and writes:

  data/processed/boamp_full_clean_nlp.csv       — full corpus + NLP columns
  data/processed/boamp_phase2_survival_nlp.csv  — survival cohort + NLP columns (join);
                                                  boamp_phase2_survival.csv is read-only here

NLP columns added:
  category_id_nlp       predicted category
  category_label_nlp    human-readable label
  nlp_confidence        max predicted probability
  nlp_low_confidence    True if nlp_confidence < 0.70
"""

import sys
import warnings
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")

CLEAN_CSV = "data/processed/boamp_full_clean.csv"
SURVIVAL_CSV = "data/processed/boamp_phase2_survival.csv"
OUT_CLEAN = "data/processed/boamp_full_clean_nlp.csv"
OUT_SURVIVAL = "data/processed/boamp_phase2_survival_nlp.csv"

MODEL_DIR = Path("models")
CONFIDENCE_THRESHOLD = 0.70

CATEGORY_LABELS = {
    "CAT01": "Software & Applications",
    "CAT02": "IT Services & Consulting",
    "CAT03": "Cybersecurity",
    "CAT04": "Telecom & Networks",
    "CAT05": "Cloud & Infrastructure",
    "CAT06": "IT Hardware & Equipment",
    "CAT07": "Digital Workplace & Collaboration",
    "CAT08": "Data & AI",
    "CAT09": "GIS & Mapping",
    "CAT10": "IT Maintenance & Support",
    "CAT_UNKNOWN": "Unknown",
}


def build_text(row: pd.Series) -> str:
    objet = str(row.get("objet", "") or "")
    desc = str(row.get("descripteur_libelle", "") or "").replace("|", " ")
    return (objet + " " + desc).strip()


def load_best_model():
    """Load SBERT if it exists, else fall back to TF-IDF baseline."""
    sbert_path = MODEL_DIR / "sbert_classifier.pkl"
    tfidf_path = MODEL_DIR / "tfidf_baseline.pkl"

    if sbert_path.exists():
        saved = joblib.load(sbert_path)
        if saved.get("winner") == "SBERT":
            print(f"Loaded SBERT model from {sbert_path}")
            return "sbert", saved
    if tfidf_path.exists():
        saved = joblib.load(tfidf_path)
        print(f"Loaded TF-IDF model from {tfidf_path} (winner: {saved.get('winner')})")
        return "tfidf", saved

    sys.exit(
        "ERROR: no trained model found in models/.\n"
        "Run nlp_baseline_classifier.py (and optionally nlp_advanced_classifier.py) first."
    )


def predict(model_type: str, saved: dict, texts: list[str]):
    """Returns (predicted_classes, max_proba)."""
    if model_type == "tfidf":
        pipe = saved["model"]
        proba = pipe.predict_proba(texts)
        classes = pipe.classes_
    else:  # sbert
        from sentence_transformers import SentenceTransformer
        print(f"  Encoding {len(texts)} texts with {saved['encoder_name']} …")
        encoder = SentenceTransformer(saved["encoder_name"])
        X_emb = encoder.encode(texts, show_progress_bar=True, batch_size=64)
        clf = saved["classifier"]
        proba = clf.predict_proba(X_emb)
        classes = clf.classes_

    pred_idx = np.argmax(proba, axis=1)
    pred_classes = classes[pred_idx]
    max_proba = proba[np.arange(len(proba)), pred_idx]
    return pred_classes, max_proba


def add_nlp_columns(df: pd.DataFrame, pred_classes, max_proba) -> pd.DataFrame:
    df = df.copy()
    df["category_id_nlp"] = pred_classes
    df["category_label_nlp"] = [CATEGORY_LABELS.get(c, c) for c in pred_classes]
    df["nlp_confidence"] = np.round(max_proba, 4)
    df["nlp_low_confidence"] = max_proba < CONFIDENCE_THRESHOLD
    return df


def main():
    print("=== NLP Label Propagation ===\n")

    # --- Load model ---
    model_type, saved = load_best_model()

    # --- Load full clean corpus ---
    df = pd.read_csv(CLEAN_CSV, low_memory=False)
    print(f"Loaded {len(df)} rows from {CLEAN_CSV}")

    texts = df.apply(build_text, axis=1).tolist()
    pred_classes, max_proba = predict(model_type, saved, texts)

    df_out = add_nlp_columns(df, pred_classes, max_proba)
    df_out.to_csv(OUT_CLEAN, index=False)
    print(f"\nSaved full corpus → {OUT_CLEAN} ({len(df_out)} rows)")

    # --- Summary stats ---
    print("\nNLP label distribution:")
    print(df_out["category_id_nlp"].value_counts().to_string())
    low_conf = df_out["nlp_low_confidence"].sum()
    pct = 100 * low_conf / len(df_out)
    print(f"\nLow-confidence rows (< {CONFIDENCE_THRESHOLD}): {low_conf} ({pct:.1f}%)")

    # --- Join NLP columns onto survival cohort ---
    if Path(SURVIVAL_CSV).exists():
        surv = pd.read_csv(SURVIVAL_CSV, low_memory=False)
        nlp_cols = ["idweb", "category_id_nlp", "category_label_nlp", "nlp_confidence", "nlp_low_confidence"]
        surv_nlp = surv.merge(df_out[nlp_cols], on="idweb", how="left")

        n_matched = surv_nlp["category_id_nlp"].notna().sum()
        print(f"\nSurvival cohort: {len(surv_nlp)} rows, {n_matched} matched with NLP labels")

        surv_nlp.to_csv(OUT_SURVIVAL, index=False)
        print(f"Saved survival cohort with NLP labels → {OUT_SURVIVAL}")
    else:
        print(f"\nWARNING: {SURVIVAL_CSV} not found — skipping survival cohort join")

    print("\nDone.")


if __name__ == "__main__":
    main()
