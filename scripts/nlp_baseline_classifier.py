"""
Phase 2 NLP — Step 1: TF-IDF Baseline Classifier

Input:  data/annotation/boamp_annotation_gold.csv
Output: models/tfidf_baseline.pkl
        reports/tables/nlp/baseline_results.csv
        reports/tables/nlp/baseline_confusion_matrix.csv
"""

import sys
import warnings
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    cohen_kappa_score,
    f1_score,
)
from sklearn.calibration import CalibratedClassifierCV

warnings.filterwarnings("ignore")

GOLD_PATH = "data/annotation/boamp_annotation_gold.csv"
MODEL_DIR = Path("models")
RESULTS_DIR = Path("reports/tables/nlp")
MODEL_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

FRENCH_STOPWORDS = [
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "au", "aux",
    "pour", "par", "sur", "avec", "dans", "à", "d", "l", "se", "sa", "son", "ses",
    "que", "qui", "est", "sont", "ce", "il", "elle", "ils", "elles", "ou", "si",
    "ne", "pas", "plus", "tout", "tous", "toute", "toutes", "être", "avoir",
    "lors", "selon", "ainsi", "entre", "dont", "cette", "cet", "ces", "leur",
    "leurs", "nous", "vous", "on", "y", "en", "n", "s", "j", "c", "m",
]


def build_text(row: pd.Series) -> str:
    objet = str(row.get("objet", "") or "")
    desc = str(row.get("descripteur_libelle", "") or "").replace("|", " ")
    return (objet + " " + desc).strip()


def load_gold(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    required = {"category_id_final"}
    if not required.issubset(df.columns):
        sys.exit(f"ERROR: gold CSV missing columns {required - set(df.columns)}")

    # Drop rows where annotation is empty or invalid
    df = df[df["category_id_final"].notna()].copy()
    df["category_id_final"] = df["category_id_final"].str.strip()
    df = df[df["category_id_final"] != ""].copy()

    valid_cats = {f"CAT{i:02d}" for i in range(1, 11)} | {"CAT_UNKNOWN"}
    unknown_labels = set(df["category_id_final"]) - valid_cats
    if unknown_labels:
        print(f"WARNING: unrecognised labels will be dropped: {unknown_labels}")
        df = df[df["category_id_final"].isin(valid_cats)]

    df["text"] = df.apply(build_text, axis=1)
    print(f"Loaded {len(df)} annotated rows, {df['category_id_final'].nunique()} classes")
    return df


def train_and_eval(df: pd.DataFrame):
    X = df["text"].tolist()
    y = df["category_id_final"].tolist()

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # --- Logistic Regression pipeline ---
    pipe_lr = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            max_features=15_000,
            sublinear_tf=True,
            min_df=1,
            stop_words=FRENCH_STOPWORDS,
        )),
        ("clf", LogisticRegression(
            C=1.0,
            class_weight="balanced",
            solver="lbfgs",
            max_iter=2000,
            multi_class="multinomial",
        )),
    ])

    # --- Linear SVM with calibration for probabilities ---
    pipe_svm = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            max_features=15_000,
            sublinear_tf=True,
            min_df=1,
            stop_words=FRENCH_STOPWORDS,
        )),
        ("clf", CalibratedClassifierCV(
            LinearSVC(C=0.5, class_weight="balanced", max_iter=2000),
            cv=3,
        )),
    ])

    results = {}
    best_pipe = None
    best_f1 = -1

    for name, pipe in [("LR", pipe_lr), ("SVM", pipe_svm)]:
        cv_scores = cross_validate(
            pipe, X, y, cv=cv,
            scoring=["f1_macro", "f1_weighted", "accuracy"],
            return_train_score=False,
        )
        macro = cv_scores["test_f1_macro"].mean()
        results[name] = {
            "macro_f1_mean": round(macro, 4),
            "macro_f1_std": round(cv_scores["test_f1_macro"].std(), 4),
            "weighted_f1_mean": round(cv_scores["test_f1_weighted"].mean(), 4),
            "accuracy_mean": round(cv_scores["test_accuracy"].mean(), 4),
        }
        print(f"  {name}: macro F1 = {macro:.4f} ± {cv_scores['test_f1_macro'].std():.4f}")
        if macro > best_f1:
            best_f1 = macro
            best_pipe = (name, pipe)

    winner_name, winner_pipe = best_pipe
    print(f"\nBest model: {winner_name} (macro F1 = {best_f1:.4f})")

    # Fit on full gold set and save
    winner_pipe.fit(X, y)
    out_path = MODEL_DIR / "tfidf_baseline.pkl"
    joblib.dump({"model": winner_pipe, "winner": winner_name, "classes": winner_pipe.classes_.tolist()}, out_path)
    print(f"Saved model → {out_path}")

    # Per-class F1 via cross_val_predict
    y_pred = cross_val_predict(winner_pipe, X, y, cv=cv)
    report = classification_report(y, y_pred, output_dict=True, zero_division=0)
    report_df = pd.DataFrame(report).T.reset_index().rename(columns={"index": "class"})

    # Cohen's kappa (model predictions vs rule-based labels, on the annotated subset)
    if "category_id_rule" in pd.read_csv(GOLD_PATH).columns:
        gold_raw = pd.read_csv(GOLD_PATH)
        gold_raw = gold_raw[gold_raw["category_id_final"].notna() & (gold_raw["category_id_final"].str.strip() != "")]
        kappa_val = cohen_kappa_score(
            gold_raw["category_id_rule"].fillna("CAT_UNKNOWN"),
            gold_raw["category_id_final"].str.strip(),
        )
        print(f"Cohen's kappa (model vs rule-based): {kappa_val:.4f}")
        results["kappa_rule_vs_gold"] = round(kappa_val, 4)

    # Save summary
    summary = pd.DataFrame(results).T.reset_index().rename(columns={"index": "model"})
    summary.to_csv(RESULTS_DIR / "baseline_results.csv", index=False)
    print(f"Saved results → {RESULTS_DIR / 'baseline_results.csv'}")

    # Confusion matrix
    classes = sorted(set(y))
    cm = confusion_matrix(y, y_pred, labels=classes)
    cm_df = pd.DataFrame(cm, index=classes, columns=classes)
    cm_df.to_csv(RESULTS_DIR / "baseline_confusion_matrix.csv")
    print(f"Saved confusion matrix → {RESULTS_DIR / 'baseline_confusion_matrix.csv'}")

    # Per-class report
    report_df.to_csv(RESULTS_DIR / "baseline_per_class.csv", index=False)
    print(f"Saved per-class report → {RESULTS_DIR / 'baseline_per_class.csv'}")

    return winner_name, best_f1


def main():
    print("=== TF-IDF Baseline Classifier ===\n")
    gold_path = Path(GOLD_PATH)
    if not gold_path.exists():
        sys.exit(
            f"ERROR: {GOLD_PATH} not found.\n"
            "Run nlp_annotation_sample.py first, fill the CSV, "
            "save as data/annotation/boamp_annotation_gold.csv"
        )

    df = load_gold(GOLD_PATH)
    print("\nClass distribution:")
    print(df["category_id_final"].value_counts().to_string())
    print()

    winner_name, best_f1 = train_and_eval(df)
    print(f"\nDone. Best model: TF-IDF + {winner_name}, macro F1 = {best_f1:.4f}")


if __name__ == "__main__":
    main()
