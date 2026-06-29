"""
Phase 2 NLP — Step 2: SBERT Advanced Classifier

Uses the sentence-transformers model already cached from renewal linking
(paraphrase-multilingual-MiniLM-L12-v2) to encode contract text, then
fits a logistic regression on top. Compared against TF-IDF baseline.

Input:  data/annotation/boamp_annotation_gold.csv
        models/tfidf_baseline.pkl  (for comparison)
Output: models/sbert_classifier.pkl  (if SBERT wins)
        reports/tables/nlp/model_comparison.csv
"""

import sys
import warnings
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator, TransformerMixin

warnings.filterwarnings("ignore")

GOLD_PATH = "data/annotation/boamp_annotation_gold.csv"
MODEL_DIR = Path("models")
RESULTS_DIR = Path("reports/tables/nlp")
SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

FRENCH_STOPWORDS = [
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "au", "aux",
    "pour", "par", "sur", "avec", "dans", "à", "d", "l", "se", "sa", "son", "ses",
]


def build_text(row: pd.Series) -> str:
    objet = str(row.get("objet", "") or "")
    desc = str(row.get("descripteur_libelle", "") or "").replace("|", " ")
    return (objet + " " + desc).strip()


def load_gold(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df[df["category_id_final"].notna()].copy()
    df["category_id_final"] = df["category_id_final"].str.strip()
    df = df[df["category_id_final"] != ""].copy()
    df["text"] = df.apply(build_text, axis=1)
    print(f"Loaded {len(df)} annotated rows, {df['category_id_final'].nunique()} classes")
    return df


class SBERTEncoder(BaseEstimator, TransformerMixin):
    """Wraps sentence-transformers for use in a sklearn pipeline."""

    def __init__(self, model_name: str = SBERT_MODEL):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"  Loading {self.model_name} …")
            self._model = SentenceTransformer(self.model_name)

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        self._load()
        return self._model.encode(list(X), show_progress_bar=False, batch_size=64)


def encode_all(texts: list[str]) -> np.ndarray:
    """Encode once and reuse — avoids re-loading model each CV fold."""
    from sentence_transformers import SentenceTransformer
    print(f"  Encoding {len(texts)} texts with {SBERT_MODEL} …")
    model = SentenceTransformer(SBERT_MODEL)
    return model.encode(texts, show_progress_bar=True, batch_size=64)


def main():
    print("=== SBERT Advanced Classifier ===\n")

    gold_path = Path(GOLD_PATH)
    if not gold_path.exists():
        sys.exit(f"ERROR: {GOLD_PATH} not found. Run nlp_annotation_sample.py and fill the CSV first.")

    df = load_gold(GOLD_PATH)
    X_text = df["text"].tolist()
    y = df["category_id_final"].tolist()

    # --- Encode once (expensive), then cross-validate on the fixed embeddings ---
    X_emb = encode_all(X_text)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    lr = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=2000,
        multi_class="multinomial",
    )

    cv_scores = cross_validate(
        lr, X_emb, y, cv=cv,
        scoring=["f1_macro", "f1_weighted", "accuracy"],
        return_train_score=False,
    )

    sbert_macro = cv_scores["test_f1_macro"].mean()
    sbert_std = cv_scores["test_f1_macro"].std()
    print(f"\nSBERT + LR: macro F1 = {sbert_macro:.4f} ± {sbert_std:.4f}")

    # --- Load TF-IDF baseline score for comparison ---
    baseline_path = MODEL_DIR / "tfidf_baseline.pkl"
    baseline_f1 = None
    baseline_name = "TF-IDF baseline"
    if baseline_path.exists():
        saved = joblib.load(baseline_path)
        results_path = RESULTS_DIR / "baseline_results.csv"
        if results_path.exists():
            res = pd.read_csv(results_path)
            if "macro_f1_mean" in res.columns:
                baseline_f1 = res["macro_f1_mean"].max()
                print(f"TF-IDF baseline: macro F1 = {baseline_f1:.4f}")

    # --- Decision: save SBERT model only if it wins by ≥ 5 F1 points ---
    THRESHOLD = 0.05
    comparison = {
        "model": ["TF-IDF baseline", "SBERT + LR"],
        "macro_f1": [
            round(baseline_f1, 4) if baseline_f1 is not None else None,
            round(sbert_macro, 4),
        ],
        "macro_f1_std": [None, round(sbert_std, 4)],
    }

    if baseline_f1 is not None:
        gain = sbert_macro - baseline_f1
        comparison["gain_vs_baseline"] = [0.0, round(gain, 4)]
        if gain >= THRESHOLD:
            print(f"\nSBERT wins by {gain:.4f} (≥ {THRESHOLD}) → using SBERT as final model")
            # Fit on full gold set and save
            lr.fit(X_emb, y)

            # We also need to save the encoder itself
            from sentence_transformers import SentenceTransformer
            encoder = SentenceTransformer(SBERT_MODEL)

            joblib.dump(
                {
                    "encoder_name": SBERT_MODEL,
                    "classifier": lr,
                    "classes": lr.classes_.tolist(),
                    "winner": "SBERT",
                },
                MODEL_DIR / "sbert_classifier.pkl",
            )
            print(f"Saved SBERT model → {MODEL_DIR / 'sbert_classifier.pkl'}")
        else:
            print(f"\nGain = {gain:.4f} < {THRESHOLD} → TF-IDF baseline is sufficient")
            print("Final model: TF-IDF baseline (models/tfidf_baseline.pkl)")
    else:
        print("\nNo baseline found to compare — saving SBERT model anyway")
        lr.fit(X_emb, y)
        from sentence_transformers import SentenceTransformer
        joblib.dump(
            {"encoder_name": SBERT_MODEL, "classifier": lr, "classes": lr.classes_.tolist(), "winner": "SBERT"},
            MODEL_DIR / "sbert_classifier.pkl",
        )

    # Per-class report via cross_val_predict
    y_pred = cross_val_predict(lr, X_emb, y, cv=cv)
    report = classification_report(y, y_pred, output_dict=True, zero_division=0)
    report_df = pd.DataFrame(report).T.reset_index().rename(columns={"index": "class"})
    report_df.to_csv(RESULTS_DIR / "sbert_per_class.csv", index=False)
    print(f"Saved per-class report → {RESULTS_DIR / 'sbert_per_class.csv'}")

    # Save comparison table
    comp_df = pd.DataFrame(comparison)
    comp_df.to_csv(RESULTS_DIR / "model_comparison.csv", index=False)
    print(f"Saved model comparison → {RESULTS_DIR / 'model_comparison.csv'}")
    print("\nComparison table:")
    print(comp_df.to_string(index=False))


if __name__ == "__main__":
    main()
