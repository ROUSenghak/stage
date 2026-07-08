from __future__ import annotations

import json
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / "notebooks" / "06_linkage_method_comparison_no_ground_truth.ipynb"
SUMMARY_PATH = ROOT / "reports" / "tables" / "validation" / "method_comparison_execution_summary.json"


def md(source: str):
    return nbf.v4.new_markdown_cell(source.strip() + "\n")


def code(source: str):
    return nbf.v4.new_code_cell(source.strip() + "\n")


def pct(x):
    return f"{100 * float(x):.1f}%"


def num(x, digits=3):
    if x is None:
        return "NA"
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return str(x)


summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8")) if SUMMARY_PATH.exists() else {}
real_counts = summary.get("real_boamp_event_counts", [])
synthetic_all = summary.get("synthetic_benchmark_metrics_all", [])
survival = summary.get("survival_results", [])
thresholds = summary.get("selected_thresholds", [])
files_created = summary.get("files_created", [])


def bullet_table(rows, cols):
    lines = []
    for row in rows:
        parts = [f"{label}: {row.get(key, 'NA')}" for label, key in cols]
        lines.append("- " + "; ".join(parts))
    return "\n".join(lines)


final_summary = f"""
## Final Executed Summary

### Why these methods were tested

BOAMP does not provide official renewal-chain ground truth, so the comparison treats the observed event as a proxy recurrence: an identifiable reappearance of a similar procurement need under a transparent matching rule. The goal is not to claim known real BOAMP precision or recall. The goal is to compare the current calibrated rule against literature-supported alternatives using synthetic truth, negative controls, manual audit evidence where available, and survival-model sufficiency.

### Methods and literature ideas

- M0: calibrated deterministic composite rule. This corresponds to rule-based record linkage with domain-engineered similarity scores and threshold calibration.
- M1: probabilistic linkage classifier. This follows the Fellegi-Sunter/probabilistic linkage idea, implemented here as a logistic match-probability model because Splink and recordlinkage were not available in the current environment.
- M2: active-learning-assisted linkage. This uses the same probabilistic feature space but incorporates mapped manual TP/FP accepted-link labels and exports a targeted review sample for uncertain or high-risk candidate pairs.

### Actual computed results

Real BOAMP event counts:
{bullet_table(real_counts, [("method", "method"), ("variant", "variant"), ("events", "event_count"), ("event_rate", "event_rate")])}

Synthetic benchmark metrics across all scenarios:
{bullet_table(synthetic_all, [("method", "method"), ("variant", "variant"), ("precision", "precision"), ("recall", "recall"), ("FP", "FP"), ("FN", "FN")])}

Survival results for the required selected runs:
{bullet_table(survival, [("method", "method"), ("variant", "variant"), ("events", "events"), ("S12", "survival_12m"), ("S24", "survival_24m"), ("S48", "survival_48m"), ("S60", "survival_60m"), ("KM median reached", "km_median_reached"), ("Cox C-index", "cox_c_index"), ("best AFT", "best_aft_model")])}

Selected thresholds:
{bullet_table(thresholds, [("method", "method"), ("variant", "variant"), ("threshold", "threshold"), ("text_threshold", "text_threshold"), ("composite_threshold", "composite_threshold"), ("margin_threshold", "margin_threshold")])}

### Recommendation

The current calibrated balanced rule remains the main method for now: {summary.get("recommendation", "NA")}. M0 balanced is retained because the project instruction is not to replace it immediately, and because the real BOAMP labels remain proxy recurrences rather than formally verified renewal-chain labels. The best alternative balanced method is included in the survival comparison as a candidate for further targeted manual review.

### Limitations

- Real BOAMP precision and recall are not directly observable.
- Synthetic benchmark labels are known only by construction and cannot certify real BOAMP legal recurrence chains.
- M1 and M2 use a logistic probability model because Splink and recordlinkage were unavailable.
- M2 uses only mapped manual TP/FP accepted-link labels; uncertain labels, false negatives, and plausible censored cases are kept as review context rather than treated as complete ground truth.
- The active-learning review sample is a prioritization output, not a completed validation result.

### Outputs generated

{chr(10).join("- " + f for f in files_created)}

### Report updates needed

- Add this method comparison as a validation/sensitivity section.
- State that M0 balanced remains the current reference method, with M1/M2 as alternatives requiring targeted manual review before replacement.
- Report synthetic precision and recall separately, not only F1.
- Report real BOAMP event counts, negative-control behavior, manual audit precision where available, and survival sufficiency without claiming known real precision/recall.
- Keep the language as proxy recurrence or identifiable reappearance of a similar procurement need, not as a formally verified renewal chain.
"""


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "pygments_lexer": "ipython3"},
}

cells = [
    md(
        """
# BOAMP Linkage Method Comparison Without Legal Ground Truth

This notebook compares the current calibrated BOAMP renewal-linking proxy-event definition with probabilistic and active-learning-assisted alternatives. The analysis is intentionally validation-oriented: BOAMP has no official renewal-chain ground truth, so real BOAMP events are treated as proxy recurrences, not formally verified renewal-chain labels.
"""
    ),
    md(
        """
## 1. Execute the Reproducible Analysis

The script below searches and loads the current project artifacts, builds the unified candidate-pair table, fits M1/M2, evaluates synthetic and real BOAMP behavior, selects broad/balanced/strict thresholds from observed grids, reruns the selected survival comparisons, writes all required tables, and prints a clear execution summary.
"""
    ),
    code(
        """
import runpy
import os
from pathlib import Path

cwd = Path.cwd()
project_root = cwd if (cwd / "scripts" / "linkage_method_comparison_no_ground_truth.py").exists() else cwd.parent
os.chdir(project_root)
runpy.run_path("scripts/linkage_method_comparison_no_ground_truth.py", run_name="__main__")
"""
    ),
    md("## 2. Files Loaded"),
    code(
        """
import pandas as pd
from pathlib import Path

pd.set_option("display.max_columns", 120)
pd.set_option("display.max_colwidth", 160)
inventory = pd.read_csv("reports/tables/validation/method_comparison_input_inventory.csv")
display(inventory)
"""
    ),
    md("## 3. Unified Candidate-Pair Table"),
    code(
        """
unified = pd.read_csv("reports/tables/validation/unified_candidate_pair_table.csv")
print(unified.shape)
display(unified.head())
display(unified.groupby("candidate_pair_dataset").size().rename("rows").reset_index())
"""
    ),
    md("## 4. Method Comparison Outputs"),
    code(
        """
real_comparison = pd.read_csv("reports/tables/validation/linkage_method_comparison.csv")
synthetic_comparison = pd.read_csv("reports/tables/validation/linkage_method_comparison_synthetic_metrics.csv")
probabilistic = pd.read_csv("reports/tables/validation/probabilistic_linkage_results.csv")
recommendation = pd.read_csv("reports/tables/validation/final_method_recommendation.csv")

display(real_comparison)
display(synthetic_comparison[synthetic_comparison["scenario"].isin(["all", "easy", "medium", "hard"])])
display(probabilistic)
display(recommendation)
"""
    ),
    md("## 5. Active-Learning Review Sample"),
    code(
        """
active_sample = pd.read_csv("reports/tables/validation/active_learning_review_sample.csv")
print(active_sample.shape)
display(active_sample.head(20))
display(active_sample["review_reason"].value_counts().rename("n_pairs").reset_index())
"""
    ),
    md("## 6. Survival Comparison"),
    code(
        """
survival = pd.read_csv("reports/tables/validation/method_survival_comparison.csv")
display(survival)
"""
    ),
    md("## 7. Figures"),
    code(
        """
from IPython.display import Image, display
for fig in [
    "reports/figures/validation/method_comparison_synthetic_precision_recall.png",
    "reports/figures/validation/method_comparison_real_event_counts.png",
    "reports/figures/validation/method_survival_km_probabilities.png",
]:
    print(fig)
    display(Image(filename=fig))
"""
    ),
    md(final_summary),
]

nb["cells"] = cells
NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, NOTEBOOK)
print(f"Wrote {NOTEBOOK.relative_to(ROOT)}")
