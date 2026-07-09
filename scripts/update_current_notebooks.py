from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip() + "\n")


def code(text: str):
    return nbf.v4.new_code_cell(text.strip() + "\n")


def write_notebook(path: Path, title: str, purpose: str, cells: list) -> None:
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python (stage-1)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    }
    header = md(
        f"""
# {title}

**Current dataset notebook.** This notebook has been refreshed for the enriched current BOAMP dataset under `data/processed/boamp_current/`.

{purpose}

Interpretation guardrail: `event = 1` is a **proxy recurrence**, meaning an identifiable reappearance of a similar procurement need under the selected rule. It is not a legally verified renewal.
"""
    )
    nb["cells"] = [header, *cells]
    nbf.write(nb, path)


SETUP = code(
    r"""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display

cwd = Path.cwd()
PROJECT = cwd
for candidate in [cwd, *cwd.parents]:
    if (candidate / "data").exists() and (candidate / "reports").exists():
        PROJECT = candidate
        break

DATA = PROJECT / "data" / "processed" / "boamp_current"
RAW = PROJECT / "data" / "raw" / "boamp_current"
TABLES = PROJECT / "reports" / "tables"
FIGURES = PROJECT / "reports" / "figures"

pd.set_option("display.max_columns", 120)
pd.set_option("display.max_colwidth", 160)

print(f"Project root: {PROJECT}")
print(f"Current data directory: {DATA}")
"""
)


LOAD_CORE = code(
    r"""
download = pd.read_csv(TABLES / "data" / "boamp_current_download_summary.csv")
enrichment = pd.read_csv(TABLES / "data" / "buyer_enrichment_summary.csv")
population_summary = pd.read_csv(TABLES / "data" / "analytical_population_summary.csv")
selected = pd.read_csv(TABLES / "linkage" / "final_selected_event_definition_current.csv")
survival = pd.read_csv(TABLES / "survival" / "survival_summary_current.csv")
risk = pd.read_csv(TABLES / "survival" / "operational_risk_scores_current.csv", dtype={"SIREN": str, "SIRET": str})

summary = {
    "study_period": download["actual_date_range"].dropna().iloc[-1],
    "retained_notices": int(download["number_of_retained_notices"].dropna().iloc[-1]),
    "appel_offre": int(enrichment.loc[enrichment["metric"].eq("APPEL_OFFRE"), "value"].iloc[0]),
    "eligible_contracts": int(selected["eligible_contracts"].iloc[0]),
    "selected_method": f"{selected['selected_method'].iloc[0]} {selected['selected_variant'].iloc[0]}",
    "proxy_events": int(selected["event_count"].iloc[0]),
    "event_rate": float(selected["event_rate"].iloc[0]),
    "censoring_date": selected["censoring_date"].iloc[0],
    "survival_24m": float(survival["survival_24m"].iloc[0]),
    "mean_p12": float(risk["p_renewal_12m"].mean()),
    "mean_p24": float(risk["p_renewal_24m"].mean()),
}
pd.DataFrame([summary])
"""
)


FIGURE_VIEW = code(
    r"""
from IPython.display import Image, display

for fig in [
    FIGURES / "data" / "analytical_population_funnel.png",
    FIGURES / "linkage" / "method_event_counts.png",
    FIGURES / "linkage" / "method_score_distributions.png",
    FIGURES / "survival" / "km_curve_current.png",
    FIGURES / "survival" / "p12_distribution_current.png",
]:
    print(fig.relative_to(PROJECT))
    if fig.exists():
        display(Image(filename=str(fig)))
    else:
        print("MISSING")
"""
)


def cells_data() -> list:
    return [
        SETUP,
        md("## Current BOAMP Download and Dataset Shape"),
        LOAD_CORE,
        code(
            r"""
clean = pd.read_csv(DATA / "boamp_full_clean_enriched.csv", dtype={"buyer_siret_clean": str, "buyer_siren_enriched": str}, low_memory=False)
download_by_year = pd.read_csv(TABLES / "data" / "boamp_current_download_summary.csv")
display(download_by_year[["year", "retained_notices", "api_total_count", "pages"]])
display(clean[["idweb", "dateparution", "nature", "buyer_key", "buyer_key_type", "cpv_clean", "category_label"]].head())
""",
        ),
        md("## Buyer Enrichment and Data Quality"),
        code(
            r"""
display(pd.read_csv(TABLES / "data" / "buyer_enrichment_summary.csv"))
display(pd.read_csv(TABLES / "data" / "buyer_key_quality_summary.csv"))
display(pd.read_csv(TABLES / "data" / "siren_siret_coverage_by_year.csv").tail())
display(pd.read_csv(TABLES / "data" / "cpv_quality_by_year.csv").tail())
display(pd.read_csv(TABLES / "data" / "duration_quality_by_year.csv").tail())
""",
        ),
        md("## Current Figures"),
        FIGURE_VIEW,
    ]


def cells_eda() -> list:
    return [
        SETUP,
        md("## Current Dataset EDA"),
        LOAD_CORE,
        code(
            r"""
clean = pd.read_csv(DATA / "boamp_full_clean_enriched.csv", parse_dates=["dateparution"], low_memory=False)
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
clean.groupby(clean["dateparution"].dt.year).size().plot.bar(ax=axes[0, 0], color="#4C78A8", title="Current notices by year")
clean["nature"].value_counts().plot.bar(ax=axes[0, 1], color="#72B7B2", title="Notice nature")
clean["buyer_key_type"].value_counts().plot.bar(ax=axes[1, 0], color="#F58518", title="Buyer key type")
clean["category_label"].fillna("Unknown").value_counts().head(10).sort_values().plot.barh(ax=axes[1, 1], color="#54A24B", title="Top segments")
plt.tight_layout()
plt.show()
""",
        ),
        code(
            r"""
display(clean.groupby("year", dropna=False).agg(
    notices=("idweb", "count"),
    appel_offre=("nature", lambda s: (s == "APPEL_OFFRE").sum()),
    attribution=("nature", lambda s: (s == "ATTRIBUTION").sum()),
    siren_or_siret=("buyer_key_type", lambda s: s.ne("NAME").sum()),
    generic_cpv=("cpv_is_generic", "sum"),
).reset_index().tail(12))
""",
        ),
    ]


def cells_linkage() -> list:
    return [
        SETUP,
        md("## Current Candidate Pairs and M0/M1/M2 Results"),
        LOAD_CORE,
        code(
            r"""
pairs = pd.read_csv(DATA / "boamp_candidate_pairs_enriched.csv", low_memory=False)
comparison = pd.read_csv(TABLES / "linkage" / "method_comparison_current_dataset.csv")
selected = pd.read_csv(TABLES / "linkage" / "final_selected_event_definition_current.csv")
display(pd.read_csv(TABLES / "linkage" / "candidate_generation_summary.csv"))
display(comparison)
display(selected)
display(pairs.sort_values("composite_score", ascending=False).head(10))
""",
        ),
        md("## Linkage Figures"),
        code(
            r"""
from IPython.display import Image, display
for fig in [
    FIGURES / "linkage" / "candidate_count_distribution.png",
    FIGURES / "linkage" / "method_event_counts.png",
    FIGURES / "linkage" / "method_score_distributions.png",
]:
    print(fig.relative_to(PROJECT))
    display(Image(filename=str(fig)))
""",
        ),
    ]


def cells_methodology() -> list:
    return [
        SETUP,
        md("## Current Methodology Tests"),
        LOAD_CORE,
        code(
            r"""
for name in [
    "classifier_benchmark_current.csv",
    "blocking_strategy_comparison_current.csv",
    "text_similarity_comparison_current.csv",
    "threshold_zone_analysis_current.csv",
    "active_learning_label_budget_current.csv",
    "subgroup_quality_audit_current.csv",
    "unique_link_constraint_diagnostics_current.csv",
    "external_reference_diagnostics_current.csv",
    "methodology_tests_summary_current.csv",
]:
    print("\n==", name, "==")
    display(pd.read_csv(TABLES / "validation" / name).head(20))
""",
        ),
    ]


def cells_survival() -> list:
    return [
        SETUP,
        md("## Current Selected Event Definition and Survival Results"),
        LOAD_CORE,
        code(
            r"""
selected = pd.read_csv(TABLES / "linkage" / "final_selected_event_definition_current.csv")
surv = pd.read_csv(TABLES / "survival" / "survival_summary_current.csv")
cox = pd.read_csv(TABLES / "survival" / "cox_results_current.csv")
aft = pd.read_csv(TABLES / "survival" / "aft_comparison_current.csv")
risk = pd.read_csv(TABLES / "survival" / "operational_risk_scores_current.csv", dtype={"SIREN": str, "SIRET": str})
display(selected)
display(surv)
display(cox.head(20))
display(aft)
display(risk.sort_values("p_renewal_12m", ascending=False).head(20))
""",
        ),
        md("## Survival and Operational Figures"),
        code(
            r"""
from IPython.display import Image, display
for fig in [
    FIGURES / "survival" / "km_curve_current.png",
    FIGURES / "survival" / "km_method_comparison_current.png",
    FIGURES / "survival" / "aft_model_comparison_current.png",
    FIGURES / "survival" / "p12_distribution_current.png",
    FIGURES / "survival" / "top_buyer_risk_current.png",
    FIGURES / "survival" / "top_segment_risk_current.png",
]:
    print(fig.relative_to(PROJECT))
    display(Image(filename=str(fig)))
""",
        ),
    ]


def cells_live() -> list:
    return [
        SETUP,
        md("## Current Gigalis Live Operational Scoring"),
        LOAD_CORE,
        code(
            r"""
live_contracts = pd.read_csv(TABLES / "survival" / "live_contract_risk_scores_current.csv", dtype={"SIREN": str, "SIRET": str})
live_buyers = pd.read_csv(TABLES / "survival" / "live_buyer_risk_ranking_current.csv")
live_segments = pd.read_csv(TABLES / "survival" / "live_segment_risk_ranking_current.csv")
display(live_contracts.head(25))
display(live_buyers.head(20))
display(live_segments.head(20))
""",
        ),
    ]


def cells_report() -> list:
    return [
        SETUP,
        md("## Current Report and Source Trace"),
        LOAD_CORE,
        code(
            r"""
source_trace = pd.read_csv(PROJECT / "reports" / "current_source_values_used.csv")
audit = pd.read_csv(TABLES / "audit" / "final_current_pipeline_audit.csv")
display(source_trace)
display(audit)
print("Current report:", PROJECT / "reports" / "current_boamp_recurrence_study_report.pdf")
""",
        ),
        FIGURE_VIEW,
    ]


def main() -> None:
    notebooks = {
        ROOT / "notebooks" / "01_datasets_explained.ipynb": (
            "Current Dataset Explanation",
            "Documents the current BOAMP download, cleaning, SIREN/SIRET enrichment, and source-of-truth files.",
            cells_data(),
        ),
        ROOT / "notebooks" / "eda_all_data.ipynb": (
            "Current BOAMP EDA",
            "Explores the enriched current BOAMP dataset. DECP and older 2015-2024 outputs are historical unless explicitly cited.",
            cells_eda(),
        ),
        ROOT / "notebooks" / "04_synthetic_boamp_benchmark.ipynb": (
            "Current Synthetic/Silver Benchmark Diagnostics",
            "Summarizes the current synthetic/silver benchmark outputs used to compare linkage methods without real BOAMP ground truth.",
            cells_methodology(),
        ),
        ROOT / "notebooks" / "05_parameter_calibration_benchmark_and_real.ipynb": (
            "Current Methodology and Threshold Diagnostics",
            "Reviews classifier, blocking, text-similarity, threshold-zone, active-learning, subgroup, and external-reference diagnostics.",
            cells_methodology(),
        ),
        ROOT / "notebooks" / "06_apply_calibrated_rules_to_real_boamp.ipynb": (
            "Apply Current Linkage Rules to Current BOAMP",
            "Loads current candidate pairs and selected event-definition outputs generated from the enriched dataset.",
            cells_linkage(),
        ),
        ROOT / "notebooks" / "06_linkage_method_comparison_no_ground_truth.ipynb": (
            "Current BOAMP Linkage Method Comparison Without Legal Ground Truth",
            "Compares M0/M1/M2 on the enriched current dataset and preserves proxy-recurrence wording.",
            cells_linkage(),
        ),
        ROOT / "notebooks" / "07_calibrated_survival_analysis.ipynb": (
            "Current BOAMP Survival Analysis",
            "Runs through the selected current proxy-event definition, KM/Cox/AFT results, and operational risk outputs.",
            cells_survival(),
        ),
        ROOT / "notebooks" / "02_survival_modeling_boamp.ipynb": (
            "Current BOAMP Survival Modeling",
            "Replaces the old survival handoff view with current selected-method survival outputs.",
            cells_survival(),
        ),
        ROOT / "notebooks" / "03_nlp_classification.ipynb": (
            "Current Segment and Text Diagnostics",
            "Uses the current enriched BOAMP dataset to inspect segment distributions and text fields; older NLP annotation outputs are historical.",
            cells_data(),
        ),
        ROOT / "boamp_renewal_linking_quality" / "boamp_renewal_linking_eda_preprocessing.ipynb": (
            "Current BOAMP Renewal-Linking Workflow",
            "Notebook front end for the current enriched candidate-pair generation and linkage-method outputs.",
            cells_linkage(),
        ),
        ROOT / "boamp_renewal_linking_quality" / "data.ipynb": (
            "Current BOAMP Report Figures and Source Trace",
            "Notebook front end for current report figures, current source trace, and final audit outputs.",
            cells_report(),
        ),
        ROOT / "validation_robustness" / "validation_robustness_analysis.ipynb": (
            "Current BOAMP Methodology Robustness Diagnostics",
            "Replaces the older threshold-robustness notebook with current validation diagnostics for the enriched dataset.",
            cells_methodology(),
        ),
    }
    for path, (title, purpose, cells) in notebooks.items():
        write_notebook(path, title, purpose, cells)
        print(f"updated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
