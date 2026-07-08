#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "final_draft"
FIG = OUT / "figures"


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * float(x):.{digits}f}\\%"


def num(x: float, digits: int = 1) -> str:
    return f"{float(x):,.{digits}f}"


def plain_pct(x: float, digits: int = 1) -> str:
    return f"{100 * float(x):.{digits}f}%"


def read_csv(rel: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / rel)


def add_source(rows, section, metric, value, source_file, column, note=""):
    rows.append(
        {
            "section": section,
            "metric": metric,
            "value": value,
            "source_file": source_file,
            "source_column_or_table": column,
            "note": note,
        }
    )


def box(ax, x, y, w, h, text, fc="#f7f9fb", ec="#2b3a42", fs=8.5):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.035",
        linewidth=1.0,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, wrap=True)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", lw=1.0, color="#2b3a42", shrinkA=4, shrinkB=4),
    )


def save_diagram(name: str, nodes: list[str], title: str, rows: int = 1):
    cols = math.ceil(len(nodes) / rows)
    fig_w = 11
    fig_h = 2.1 * rows + 0.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_axis_off()
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.text(0, rows + 0.05, title, fontsize=11, fontweight="bold", va="bottom")
    positions = []
    for i, label in enumerate(nodes):
        r = rows - 1 - (i // cols)
        c = i % cols
        x = c + 0.08
        y = r + 0.22
        w = 0.78
        h = 0.42
        box(ax, x, y, w, h, label)
        positions.append((x, y, w, h))
    for i in range(len(positions) - 1):
        x, y, w, h = positions[i]
        x2, y2, w2, h2 = positions[i + 1]
        if (i + 1) % cols == 0 and rows > 1:
            continue
        arrow(ax, x + w, y + h / 2, x2, y2 + h2 / 2)
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_funnel(counts):
    labels = ["Raw notices", "APPEL_OFFRE", "Eligible", "M2 events", "Censored"]
    values = [
        counts["raw_notices"],
        counts["appel_offre"],
        counts["eligible"],
        counts["m2_events"],
        counts["m2_censored"],
    ]
    colors = ["#58728a", "#6f8fb0", "#89a978", "#c27d58", "#b7bec8"]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel("Rows / contracts")
    ax.set_title("Analytical population funnel")
    ax.grid(axis="y", alpha=0.25)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:,}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "fig_dataset_funnel.pdf")
    fig.savefig(FIG / "fig_dataset_funnel.png", dpi=220)
    plt.close(fig)


def copy_existing_figures():
    mapping = {
        "reports/figures/validation/method_comparison_synthetic_precision_recall.png": "fig_synthetic_precision_recall.png",
        "reports/figures/validation/method_comparison_real_event_counts.png": "fig_real_event_counts_by_method.png",
        "reports/figures/survival/calibrated_rules_km_curves.png": "fig_km_method_comparison.png",
        "reports/figures/survival/pred_hist_p12m_m2_balanced.png": "fig_m2_risk_distribution.png",
        "reports/figures/survival/pred_top20_contracts_m2_balanced.png": "fig_top_contracts_m2_balanced.png",
    }
    for src, dst in mapping.items():
        shutil.copyfile(ROOT / src, FIG / dst)


def latex_escape(s: str) -> str:
    return (
        str(s)
        .replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    full = read_csv("data/processed/boamp_full_clean.csv")
    m2 = read_csv("data/processed/boamp_phase2_survival_method_m2_balanced.csv")
    m0 = read_csv("data/processed/boamp_phase2_survival_method_m0_balanced.csv")
    m0s = read_csv("data/processed/boamp_phase2_survival_method_m0_strict.csv")
    old = read_csv("data/processed/boamp_phase2_survival.csv")
    rec = read_csv("reports/tables/validation/final_method_recommendation.csv").iloc[0]
    comp = read_csv("reports/tables/validation/linkage_method_comparison.csv")
    syn = read_csv("reports/tables/validation/linkage_method_comparison_synthetic_metrics.csv")
    surv = read_csv("reports/tables/validation/method_survival_comparison.csv")
    prob = read_csv("reports/tables/validation/probabilistic_linkage_results.csv")
    cox = read_csv("reports/tables/survival/calibrated_rule_cox_comparison.csv")
    ph = read_csv("reports/tables/survival/m2_balanced_cox_ph_assumption_test.csv")
    aft = read_csv("reports/tables/survival/m2_balanced_aft_comparison.csv")
    risk = read_csv("reports/tables/survival/renewal_risk_12_24_months_m2_balanced.csv")
    buyers = read_csv("reports/tables/survival/buyer_renewal_risk_ranking_m2_balanced.csv")
    segments = read_csv("reports/tables/survival/segment_renewal_risk_ranking_m2_balanced.csv")
    top_contracts = read_csv("reports/tables/survival/top20_renewal_risk_m2_balanced.csv")
    inventory = read_csv("reports/tables/validation/method_comparison_input_inventory.csv")
    noise = read_csv("reports/tables/validation/synthetic_noise_audit.csv")

    selected = f"{rec.selected_method} {rec.selected_variant}"
    selected_row = comp[(comp.method == rec.selected_method) & (comp.variant == rec.selected_variant)].iloc[0]
    m0_row = comp[(comp.method == "M0") & (comp.variant == "balanced")].iloc[0]
    m1_row = comp[(comp.method == "M1") & (comp.variant == "balanced")].iloc[0]
    strict_row = comp[(comp.method == "M0") & (comp.variant == "strict")].iloc[0]
    broad_row = comp[(comp.method == "M0") & (comp.variant == "broad")].iloc[0]
    surv_m2 = surv[(surv.method == "M2") & (surv.variant == "balanced")].iloc[0]
    surv_m0 = surv[(surv.method == "M0") & (surv.variant == "balanced")].iloc[0]
    surv_strict = surv[(surv.method == "M0") & (surv.variant == "strict")].iloc[0]
    prob_m2 = prob[(prob.method == "M2") & (prob.variant == "balanced")].iloc[0]
    rich_c_m2 = float(cox[cox.rule_name == "m2_balanced"].c_index.iloc[0])
    rich_c_m0 = float(cox[cox.rule_name == "balanced"].c_index.iloc[0])
    ph_decl = ph[ph.variable == "declared_duration_months"].iloc[0]
    ph_imp = ph[ph.variable == "dur_was_imputed"].iloc[0]
    ph_year = ph[ph.variable == "start_year"].iloc[0]
    aft_logn = aft[aft.model == "LogNormalAFT"].iloc[0]

    counts = {
        "raw_notices": len(full),
        "appel_offre": int((full.nature == "APPEL_OFFRE").sum()),
        "eligible": len(m2),
        "m2_events": int(m2.event.sum()),
        "m2_censored": int((m2.event == 0).sum()),
    }
    save_funnel(counts)
    copy_existing_figures()
    save_diagram(
        "fig_pipeline_overview",
        [
            "BOAMP raw notices",
            "Cleaning and enrichment",
            "Eligible APPEL_OFFRE contracts",
            "Candidate pairs",
            "Synthetic benchmark calibration",
            "M0/M1/M2 comparison",
            "Selected M2 balanced dataset",
            "Survival analysis",
            "12/24-month indicators",
        ],
        "Real BOAMP pipeline and validation flow",
        rows=3,
    )
    save_diagram(
        "fig_proxy_event_construction",
        [
            "Source contract i",
            "Expected end date",
            "6-month candidate window",
            "Same-buyer candidates",
            "Text/CPV/time/buyer features",
            "M2 match probability",
            "event = 1 or censored",
        ],
        "Proxy-event construction",
        rows=2,
    )
    save_diagram(
        "fig_no_ground_truth_validation_framework",
        [
            "Real BOAMP has no labels",
            "Synthetic benchmark has known truth",
            "Negative-control diagnostic",
            "Baseline-biased manual audit diagnostic",
            "Method comparison",
            "Selected proxy-event rule",
        ],
        "No-ground-truth validation framework",
        rows=2,
    )
    save_diagram(
        "fig_m0_m1_m2_method_logic",
        [
            "M0 deterministic composite score",
            "M1 synthetic-trained match probability",
            "M2 probability model plus review queue",
            "M2 balanced selected",
            "M0 balanced retained as baseline",
        ],
        "Method logic",
        rows=1,
    )
    save_diagram(
        "fig_survival_modeling_workflow",
        [
            "Selected M2 event definition",
            "Events and censored rows",
            "Observed duration",
            "Kaplan-Meier / Cox / AFT",
            "Fixed-horizon p12/p24",
            "Buyer, segment, contract rankings",
        ],
        "Survival modeling workflow",
        rows=2,
    )

    rows = []
    add_source(rows, "selection", "selected_method", selected, "reports/tables/validation/final_method_recommendation.csv", "selected_method, selected_variant")
    add_source(rows, "selection", "M2_match_probability_threshold", str(prob_m2.threshold), "reports/tables/validation/probabilistic_linkage_results.csv", "threshold")
    add_source(rows, "selection", "final_dataset_path", surv_m2.survival_dataset, "reports/tables/validation/method_survival_comparison.csv", "survival_dataset")
    add_source(rows, "population", "raw_BOAMP_notices", counts["raw_notices"], "data/processed/boamp_full_clean.csv", "row_count")
    add_source(rows, "population", "APPEL_OFFRE_notices", counts["appel_offre"], "data/processed/boamp_full_clean.csv", "nature == APPEL_OFFRE")
    add_source(rows, "population", "study_start_date", str(pd.to_datetime(full.dateparution).min().date()), "data/processed/boamp_full_clean.csv", "dateparution")
    add_source(rows, "population", "study_end_or_censoring_date", str(pd.to_datetime(full.dateparution).max().date()), "data/processed/boamp_full_clean.csv", "dateparution")
    add_source(rows, "population", "eligible_contracts", counts["eligible"], "data/processed/boamp_phase2_survival_method_m2_balanced.csv", "row_count")
    add_source(rows, "population", "selected_M2_events", counts["m2_events"], "data/processed/boamp_phase2_survival_method_m2_balanced.csv", "event")
    add_source(rows, "population", "selected_M2_censored", counts["m2_censored"], "data/processed/boamp_phase2_survival_method_m2_balanced.csv", "event == 0")
    add_source(rows, "historical", "old_pre_calibration_events", int(old.event.sum()), "data/processed/boamp_phase2_survival.csv", "event", "historical pre-calibration baseline only")
    add_source(rows, "historical", "old_pre_calibration_event_rate", plain_pct(old.event.mean()), "data/processed/boamp_phase2_survival.csv", "event")
    for label, r in [("M0 balanced", m0_row), ("M1 balanced", m1_row), ("M2 balanced", selected_row), ("M0 strict", strict_row), ("M0 broad", broad_row)]:
        add_source(rows, "method_comparison", f"{label} real_event_count", int(r.event_count), "reports/tables/validation/linkage_method_comparison.csv", "event_count")
        add_source(rows, "method_comparison", f"{label} real_event_rate", plain_pct(r.event_rate), "reports/tables/validation/linkage_method_comparison.csv", "event_rate")
        add_source(rows, "method_comparison", f"{label} negative_control_acceptance", plain_pct(r.negative_control_acceptance_rate), "reports/tables/validation/linkage_method_comparison.csv", "negative_control_acceptance_rate")
        add_source(rows, "method_comparison", f"{label} generic_CPV_share", plain_pct(r.generic_cpv_share), "reports/tables/validation/linkage_method_comparison.csv", "generic_cpv_share")
    for method in ["M0", "M1", "M2"]:
        for scenario in ["all", "easy", "medium", "hard", "generic_cpv", "non_generic_cpv"]:
            r = syn[(syn.method == method) & (syn.variant == "balanced") & (syn.scenario == scenario)].iloc[0]
            add_source(rows, "synthetic_benchmark", f"{method} balanced {scenario} precision", f"{r.precision:.3f}", "reports/tables/validation/linkage_method_comparison_synthetic_metrics.csv", "precision")
            add_source(rows, "synthetic_benchmark", f"{method} balanced {scenario} recall", f"{r.recall:.3f}", "reports/tables/validation/linkage_method_comparison_synthetic_metrics.csv", "recall")
            add_source(rows, "synthetic_benchmark", f"{method} balanced {scenario} F1", f"{r.F1:.3f}", "reports/tables/validation/linkage_method_comparison_synthetic_metrics.csv", "F1")
    add_source(rows, "validation", "manual_audit_sample_rows", 150, "event_validation/outputs/manual_validation_audit_labeled.csv", "row_count", "baseline-biased diagnostic")
    add_source(rows, "validation", "M2_mapped_audit_decided_n", int(selected_row.manual_audit_decided_n), "reports/tables/validation/linkage_method_comparison.csv", "manual_audit_decided_n", "diagnostic only")
    add_source(rows, "validation", "M2_mapped_audit_precision", f"{selected_row.manual_audit_precision:.3f}", "reports/tables/validation/linkage_method_comparison.csv", "manual_audit_precision", "diagnostic only")
    add_source(rows, "validation", "M0_synthetic_real_profile_shift", f"{rec.m0_synthetic_real_text_shift:.3f}", "reports/tables/validation/final_method_recommendation.csv", "m0_synthetic_real_text_shift")
    add_source(rows, "validation", "M2_synthetic_real_profile_shift", f"{rec.best_alternative_synthetic_real_text_shift:.3f}", "reports/tables/validation/final_method_recommendation.csv", "best_alternative_synthetic_real_text_shift")
    for _, r in surv.iterrows():
        label = f"{r.method} {r.variant}"
        add_source(rows, "survival", f"{label} n", int(r.n), "reports/tables/validation/method_survival_comparison.csv", "n")
        add_source(rows, "survival", f"{label} events", int(r.events), "reports/tables/validation/method_survival_comparison.csv", "events")
        add_source(rows, "survival", f"{label} survival_12m", plain_pct(r.survival_12m), "reports/tables/validation/method_survival_comparison.csv", "survival_12m")
        add_source(rows, "survival", f"{label} survival_24m", plain_pct(r.survival_24m), "reports/tables/validation/method_survival_comparison.csv", "survival_24m")
        add_source(rows, "survival", f"{label} survival_48m", plain_pct(r.survival_48m), "reports/tables/validation/method_survival_comparison.csv", "survival_48m")
        add_source(rows, "survival", f"{label} survival_60m", plain_pct(r.survival_60m), "reports/tables/validation/method_survival_comparison.csv", "survival_60m")
        add_source(rows, "survival", f"{label} reduced_Cox_C_index", f"{r.cox_c_index:.3f}", "reports/tables/validation/method_survival_comparison.csv", "cox_c_index")
    add_source(rows, "survival", "M2 richer_category_aware_Cox_C_index", f"{rich_c_m2:.3f}", "reports/tables/survival/calibrated_rule_cox_comparison.csv", "c_index")
    add_source(rows, "survival", "M0 richer_category_aware_Cox_C_index", f"{rich_c_m0:.3f}", "reports/tables/survival/calibrated_rule_cox_comparison.csv", "c_index")
    add_source(rows, "survival", "M2 best_AFT_model_headline", surv_m2.best_aft_model, "reports/tables/validation/method_survival_comparison.csv", "best_aft_model")
    add_source(rows, "survival", "M2 best_AFT_AIC_headline", f"{surv_m2.best_aft_aic:.1f}", "reports/tables/validation/method_survival_comparison.csv", "best_aft_aic", "final method-comparison headline")
    add_source(rows, "survival", "M2 LogNormalAFT_AIC_refit_table", f"{aft_logn.AIC:.1f}", "reports/tables/survival/m2_balanced_aft_comparison.csv", "AIC", "separate AFT refit table; differs slightly from headline")
    add_source(rows, "survival", "M2 PH declared_duration_p", f"{ph_decl.p:.3g}", "reports/tables/survival/m2_balanced_cox_ph_assumption_test.csv", "p")
    add_source(rows, "survival", "M2 PH dur_was_imputed_p", f"{ph_imp.p:.3g}", "reports/tables/survival/m2_balanced_cox_ph_assumption_test.csv", "p")
    add_source(rows, "survival", "M2 PH start_year_p", f"{ph_year.p:.3g}", "reports/tables/survival/m2_balanced_cox_ph_assumption_test.csv", "p")
    add_source(rows, "operational", "risk_indicator_rows", len(risk), "reports/tables/survival/renewal_risk_12_24_months_m2_balanced.csv", "row_count")
    add_source(rows, "operational", "median_p12", f"{risk.p_renewal_12m.median():.4f}", "reports/tables/survival/renewal_risk_12_24_months_m2_balanced.csv", "p_renewal_12m")
    add_source(rows, "operational", "median_p24", f"{risk.p_renewal_24m.median():.4f}", "reports/tables/survival/renewal_risk_12_24_months_m2_balanced.csv", "p_renewal_24m")
    add_source(rows, "operational", "expected_12m_recurrences", f"{risk.p_renewal_12m.sum():.1f}", "reports/tables/survival/renewal_risk_12_24_months_m2_balanced.csv", "sum(p_renewal_12m)")
    add_source(rows, "operational", "expected_24m_recurrences", f"{risk.p_renewal_24m.sum():.1f}", "reports/tables/survival/renewal_risk_12_24_months_m2_balanced.csv", "sum(p_renewal_24m)")
    add_source(rows, "operational", "top_buyer_expected_24m", f"{buyers.expected_renewals_24m.iloc[0]:.1f}", "reports/tables/survival/buyer_renewal_risk_ranking_m2_balanced.csv", "expected_renewals_24m")
    add_source(rows, "operational", "top_segment_expected_24m", f"{segments.expected_renewals_24m.iloc[0]:.1f}", "reports/tables/survival/segment_renewal_risk_ranking_m2_balanced.csv", "expected_renewals_24m")
    pd.DataFrame(rows).to_csv(OUT / "source_values_used.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    method_rows = []
    for method in ["M0", "M1", "M2"]:
        r = comp[(comp.method == method) & (comp.variant == "balanced")].iloc[0]
        s = syn[(syn.method == method) & (syn.variant == "balanced") & (syn.scenario == "all")].iloc[0]
        c = surv[(surv.method == method) & (surv.variant == "balanced")]
        cind = "--" if c.empty else f"{c.iloc[0].cox_c_index:.3f}"
        role = "selected main" if method == "M2" else ("conservative baseline" if method == "M0" else "alternative")
        method_rows.append(
            f"{method} balanced & {s.precision:.3f} & {s.recall:.3f} & {s.F1:.3f} & {int(r.event_count)} & {pct(r.event_rate)} & {pct(r.negative_control_acceptance_rate)} & {cind} & {role} \\\\"
        )
    scenario_rows = []
    for method in ["M0", "M1", "M2"]:
        parts = []
        for scenario in ["easy", "medium", "hard", "generic_cpv"]:
            r = syn[(syn.method == method) & (syn.variant == "balanced") & (syn.scenario == scenario)].iloc[0]
            parts.append(f"{r.precision:.3f}/{r.recall:.3f}/{r.F1:.3f}")
        scenario_rows.append(f"{method} balanced & " + " & ".join(parts) + r" \\")

    pop_table = rf"""
\begin{{tabular}}{{lrrl}}
\toprule
Step & Count & Share of previous & Source \\
\midrule
Raw BOAMP notices & {counts['raw_notices']:,} & -- & boamp\_full\_clean.csv \\
APPEL\_OFFRE notices & {counts['appel_offre']:,} & {pct(counts['appel_offre']/counts['raw_notices'])} & boamp\_full\_clean.csv \\
Eligible contracts & {counts['eligible']:,} & {pct(counts['eligible']/counts['appel_offre'])} & M2 survival input \\
Selected M2 proxy events & {counts['m2_events']:,} & {pct(counts['m2_events']/counts['eligible'])} & M2 survival input \\
Censored rows & {counts['m2_censored']:,} & {pct(counts['m2_censored']/counts['eligible'])} & M2 survival input \\
\bottomrule
\end{{tabular}}
"""

    top_buyer_rows = "\n".join(
        f"{latex_escape(r.buyer_key)} & {int(r.n_contracts)} & {r.expected_renewals_12m:.1f} & {r.expected_renewals_24m:.1f} \\\\"
        for _, r in buyers.head(6).iterrows()
    )
    top_segment_rows = "\n".join(
        f"{latex_escape(r.category_label)} & {int(r.n_contracts)} & {r.expected_renewals_12m:.1f} & {r.expected_renewals_24m:.1f} \\\\"
        for _, r in segments.head(6).iterrows()
    )
    top_contract_rows = "\n".join(
        f"{latex_escape(r.contract_id)} & {latex_escape(r.category_label)} & {r.p_renewal_12m:.4f} & {r.p_renewal_24m:.4f} \\\\"
        for _, r in top_contracts.head(8).iterrows()
    )

    limitations_rows = r"""
No real BOAMP ground truth & Real precision and recall cannot be observed directly & Report proxy recurrence only; use method-neutral review next \\
Synthetic benchmark is controlled, not real truth & Benchmark-estimated metrics may not transfer perfectly & Treat as calibration evidence, not proof \\
Manual audit baseline bias & Mapped audit precision is not a final arbiter & Use as plausibility diagnostic only \\
Active-learning review sample not completed & M2 review queue has not become validation labels & Complete method-neutral manual review \\
Generic CPV risk & Higher M2 generic-CPV share may hide weaker semantic evidence & Review generic-CPV M2 links first \\
Buyer fragmentation remains & Same organization can appear under multiple buyer keys & Continue SIREN/SIRET enrichment and matching checks \\
Declared duration is administrative and violates PH & Reduced Cox assumptions are partly strained & Prefer AFT and fixed-horizon indicators for operations \\
Cox C-index is weak-to-moderate & Ranking power is useful but limited & Present risk scores as prioritization, not certainty \\
Supervised NLP classifier handled separately & Segment labels are provisional in this survival work & Integrate final team NLP labels when available \\
Trend/change-point analysis remains future work & The report does not yet model demand shifts over calendar time & Add Phase 4 trend analysis later \\
"""

    tex = rf"""\documentclass[11pt,a4paper]{{article}}
\usepackage[margin=1in]{{geometry}}
\usepackage{{graphicx}}
\usepackage{{booktabs}}
\usepackage{{tabularx}}
\usepackage{{longtable}}
\usepackage{{array}}
\usepackage{{hyperref}}
\usepackage{{float}}
\usepackage{{caption}}
\usepackage{{xcolor}}
\usepackage{{enumitem}}
\usepackage{{microtype}}
\usepackage{{url}}
\setlist{{nosep}}
\hypersetup{{colorlinks=true,linkcolor=black,urlcolor=blue,citecolor=black}}
\newcolumntype{{Y}}{{>{{\raggedright\arraybackslash}}X}}
\title{{From BOAMP Notices to Procurement-Recurrence Risk:\\A Proxy-Event and Survival-Analysis Framework for Gigalis}}
\author{{First draft synthesis report}}
\date{{Generated from executed project outputs on 2026-07-08}}

\begin{{document}}
\maketitle
\begin{{abstract}}
This synthesis turns the BOAMP analysis into one coherent argument for Gigalis. It separates the business question, the absence of official renewal-chain labels, the construction of a proxy recurrence event, the benchmark and diagnostic validation layers, the M0/M1/M2 method comparison, and the survival outputs used for 12- and 24-month operational prioritization. All reported values are traced in \texttt{{source\_values\_used.csv}}.
\end{{abstract}}
\tableofcontents
\clearpage

\section{{Executive Summary}}
Gigalis wants to anticipate future public digital procurement needs early enough to prepare account monitoring, segment planning, and commercial responses. BOAMP is useful for this objective because it records public notices over time, but it is not a contract-history database and it does not contain an official field linking an older call for tender to a later renewal.

The current selected event definition is \textbf{{{selected}}} with match-probability threshold {prob_m2.threshold}. The final selected survival input is the M2 balanced survival CSV listed in the trace file. It contains {counts['eligible']:,} eligible contracts, {counts['m2_events']:,} proxy recurrence events, and {counts['m2_censored']:,} censored rows, giving an event rate of {pct(selected_row.event_rate)}. The event is an identifiable reappearance of a similar procurement need; it is not a verified legal renewal.

The selected M2 balanced method is benchmark-preferred over M0 balanced: benchmark-estimated precision/recall/F1 are {syn[(syn.method=="M2") & (syn.variant=="balanced") & (syn.scenario=="all")].precision.iloc[0]:.3f}/{syn[(syn.method=="M2") & (syn.variant=="balanced") & (syn.scenario=="all")].recall.iloc[0]:.3f}/{syn[(syn.method=="M2") & (syn.variant=="balanced") & (syn.scenario=="all")].F1.iloc[0]:.3f}, compared with {syn[(syn.method=="M0") & (syn.variant=="balanced") & (syn.scenario=="all")].precision.iloc[0]:.3f}/{syn[(syn.method=="M0") & (syn.variant=="balanced") & (syn.scenario=="all")].recall.iloc[0]:.3f}/{syn[(syn.method=="M0") & (syn.variant=="balanced") & (syn.scenario=="all")].F1.iloc[0]:.3f} for M0 balanced. M0 balanced remains the conservative transparent baseline with {int(m0_row.event_count)} events and {pct(m0_row.event_rate)}. The old {int(old.event.sum())}-event result is historical pre-calibration only.

Under M2 balanced, the Kaplan-Meier median is not reached because fewer than half of contracts experience the selected proxy event before censoring. Estimated survival is {pct(surv_m2.survival_12m)} at 12 months, {pct(surv_m2.survival_24m)} at 24 months, {pct(surv_m2.survival_48m)} at 48 months, and {pct(surv_m2.survival_60m)} at 60 months. The reduced Cox C-index is {surv_m2.cox_c_index:.3f}; the richer category-aware Cox specification has C-index {rich_c_m2:.3f}. LogNormalAFT is the best AFT model in the method-comparison output, with AIC {surv_m2.best_aft_aic:.1f}. Operational indicators are available for {len(risk):,} contracts; median p12 is {risk.p_renewal_12m.median():.4f}, median p24 is {risk.p_renewal_24m.median():.4f}, and expected proxy recurrences are {risk.p_renewal_12m.sum():.1f} at 12 months and {risk.p_renewal_24m.sum():.1f} at 24 months.

\section{{Internship and Business Context}}
The internship project supports Gigalis in moving from retrospective procurement observation to forward-looking monitoring. The practical question is not only whether a buyer has purchased digital services before, but when a similar need may reappear and which buyers, segments, or contracts deserve attention during the next 12 to 24 months.

The output is therefore designed as a prioritization layer. It can help analysts and account managers decide where to monitor BOAMP publications, where to prepare domain expertise, and which digital segments may require earlier commercial preparation. The result should not be read as a deterministic renewal forecast. It is a structured risk indicator for observable BOAMP proxy recurrences.

\section{{Data Source and Analytical Population}}
BOAMP notices provide the public procurement corpus. The survival unit is the \texttt{{APPEL\_OFFRE}} notice because it represents the initial procurement opportunity whose later recurrence is being monitored. \texttt{{ATTRIBUTION}} notices are not treated as separate survival units; they are used for start-date refinement where available because award information can improve the timing of the original contract.

The current processed BOAMP file covers publication dates from {pd.to_datetime(full.dateparution).min().date()} to {pd.to_datetime(full.dateparution).max().date()}. For the selected survival input, start dates run from {pd.to_datetime(m2.start_date).min().date()} to {pd.to_datetime(m2.start_date).max().date()}. Rows are eligible when they have enough duration and timing information to define an observation window and either a selected proxy event or right-censoring.

\begin{{table}}[H]
\centering
\caption{{Analytical population funnel. Source: executed BOAMP processed and selected M2 survival outputs.}}
{pop_table}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.82\linewidth]{{figures/fig_dataset_funnel.pdf}}
\caption{{Dataset funnel based on real BOAMP outputs. Source: generated from the executed project pipeline and validation outputs.}}
\end{{figure}}

\section{{Core Methodological Challenge: No Ground Truth}}
BOAMP has no official renewal-chain ground truth. There is no field that reliably says one call for tender is the renewal of another, and real BOAMP precision and recall are therefore not directly observable. This matters because a later notice from the same buyer may be a genuine reappearance of a similar need, a related but different procurement, a publication artefact, or an unrelated requirement.

In this report, \textbf{{event = 1}} means a proxy recurrence under the selected rule: an identifiable reappearance of a similar procurement need. \textbf{{event = 0}} means censored or no observed proxy recurrence under the available data and rule. Neither label is legal ground truth. The validation vocabulary is therefore deliberately conservative: benchmark-estimated precision/recall, diagnostic evidence, negative-control diagnostics, and method-neutral review.

\section{{Data Cleaning and Feature Construction}}
The pipeline converts notice-level BOAMP data into a contract-level survival dataset. Buyer keys are constructed from available organization identifiers and cleaned buyer names; SIREN/SIRET enrichment helps reduce buyer fragmentation but does not eliminate it. CPV codes are normalized into division and category features, and generic CPV codes are flagged because broad codes such as software or IT services can create ambiguous links.

Duration cleaning preserves the raw duration when possible, flags suspicious values, and imputes administrative durations only when needed for survival construction. Start dates are built from publication dates and refined by attribution dates where available. Sentence-Transformer embeddings provide semantic similarity between source and candidate procurement objects. The technology taxonomy is provisional and based on CPV/keyword logic; supervised NLP classification is handled separately by the team and does not block the survival pipeline.

\section{{Initial Baseline Method and Why It Was Replaced}}
The initial baseline linked notices using semantic similarity, buyer agreement, CPV evidence, and timing around the expected end date. It produced {int(old.event.sum())} events among {len(old):,} eligible contracts, an event rate of {pct(old.event.mean())}. This high-linkage result was useful for exploration, but it maximized link quantity rather than analytical reliability.

Manual audit evidence showed low precision in parts of that baseline. Later analysis also showed that the manual audit sample was itself baseline-biased because it was stratified on the pre-calibration baseline's own links and confidence tiers. The project therefore changed objective: instead of maximizing the number of links, it constructs a calibrated proxy-event definition with transparent benchmark and diagnostic evidence. The {int(old.event.sum())}-event result is retained only as a historical pre-calibration baseline.

\section{{Synthetic BOAMP-like Benchmark}}
The synthetic benchmark was needed because real BOAMP labels are unavailable. It creates BOAMP-like source and candidate pairs where the matching truth is known by construction. That makes it possible to estimate precision, recall, and F1 for candidate linkage rules without pretending that real BOAMP truth is observed.

The benchmark simulates buyer-name variation, generic CPV, CPV drift, missing CPV, missing duration, paraphrased text, timing shifts, and ambiguous same-buyer candidates. It uses easy, medium, and hard scenarios. The noise audit reports buyer-name-noise rates from {plain_pct(noise.buyer_name_noise_rate_observed.min())} to {plain_pct(noise.buyer_name_noise_rate_observed.max())}, generic-CPV rates from {plain_pct(noise.generic_cpv_rate_observed.min())} to {plain_pct(noise.generic_cpv_rate_observed.max())}, and missing-duration rates from {plain_pct(noise.missing_duration_rate_observed_sources.min())} to {plain_pct(noise.missing_duration_rate_observed_sources.max())} across scenarios.

\begin{{table}}[H]
\centering
\caption{{Balanced-method synthetic benchmark performance by scenario, shown as precision/recall/F1. Source: synthetic benchmark outputs.}}
\small
\begin{{tabular}}{{lcccc}}
\toprule
Method & Easy & Medium & Hard & Generic CPV \\
\midrule
{chr(10).join(scenario_rows)}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.72\linewidth]{{figures/fig_synthetic_precision_recall.png}}
\caption{{Synthetic precision-recall comparison for M0, M1, and M2. This is a controlled synthetic benchmark, not real BOAMP ground truth. Source: generated from the executed validation outputs.}}
\end{{figure}}

\section{{Linkage Method Comparison: M0, M1, M2}}
M0 is the deterministic calibrated composite rule. It combines text similarity, CPV compatibility, timing, and buyer logic into transparent thresholds. M1 is a probabilistic linkage model trained on synthetic pair labels in the same feature space. M2 is an active-learning-assisted variant using the same probability feature space and producing a targeted review queue.

The current final recommendation promotes M2 balanced to the main method because all promotion criteria pass: the selection score is {rec.best_alternative_score:.3f} versus {rec.m0_balanced_score:.3f} for M0 balanced; negative-control acceptance is lower than M0; the event count remains sufficient for survival; the synthetic-real profile shift is acceptable; and the text backend matches the real pipeline. Mapped audit precision is not used for final selection because the audit sample is baseline-biased. It remains a plausibility diagnostic only.

\begin{{table}}[H]
\centering
\caption{{Method comparison. Synthetic metrics are benchmark-estimated; real event counts are proxy recurrences in BOAMP.}}
\small
\resizebox{{\linewidth}}{{!}}{{%
\begin{{tabular}}{{lrrrrrrrl}}
\toprule
Method & Prec. & Rec. & F1 & Events & Event rate & Neg. control & Cox C & Role \\
\midrule
{chr(10).join(method_rows)}
\bottomrule
\end{{tabular}}
}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.75\linewidth]{{figures/fig_real_event_counts_by_method.png}}
\caption{{Real BOAMP proxy-event counts by method. Counts are constructed proxy events, not verified legal renewals. Source: generated from executed method-comparison outputs.}}
\end{{figure}}

\section{{Final Selected Event Definition}}
The final selected definition is \textbf{{M2 balanced}}, a match-probability rule at threshold {prob_m2.threshold}. The final dataset is \texttt{{data/processed/boamp\_phase2\_survival\_method\_m2\_balanced.csv}} with {counts['eligible']:,} eligible contracts, {counts['m2_events']:,} events, {pct(selected_row.event_rate)} event rate, and {counts['m2_censored']:,} censored rows.

M0 balanced remains the conservative transparent baseline: {int(m0_row.event_count)} events, {pct(m0_row.event_rate)}, and negative-control acceptance {pct(m0_row.negative_control_acceptance_rate)}. M0 strict is a high-confidence sensitivity with {int(strict_row.event_count)} events and {pct(strict_row.event_rate)}. Broad rules are high-recall sensitivity checks. The old {int(old.event.sum())}-event result is historical pre-calibration only.

\begin{{figure}}[H]
\centering
\includegraphics[width=.95\linewidth]{{figures/fig_pipeline_overview.pdf}}
\caption{{Real BOAMP pipeline from raw notices to operational indicators. Source: generated from the executed project pipeline and validation outputs.}}
\end{{figure}}

\section{{Survival-Analysis Methodology}}
The selected event definition creates a right-censored survival dataset. Each row has an observed duration: either the time from source start to the selected proxy recurrence, or the time from source start to censoring when no proxy recurrence is observed. Kaplan-Meier estimates the survival curve without assuming a parametric shape. Cox PH estimates relative hazard under proportional-hazard assumptions and reports C-index as a ranking-quality diagnostic. AFT models estimate parametric survival time distributions and are compared by AIC within the same event definition.

Fixed-horizon 12- and 24-month predictions translate the survival model into operational prioritization scores. These scores estimate identifiable BOAMP proxy recurrences under the model, not legal renewal probabilities. AIC values are comparable within the same event definition and specification; they should not be used to claim that one event definition is legally truer than another.

\begin{{figure}}[H]
\centering
\includegraphics[width=.9\linewidth]{{figures/fig_survival_modeling_workflow.pdf}}
\caption{{Survival modeling workflow for the selected M2 proxy-event definition. Source: generated from the executed project pipeline and validation outputs.}}
\end{{figure}}

\section{{Survival Results Under the Selected Method}}
Under M2 balanced, there are {int(surv_m2.events)} events among {int(surv_m2.n)} contracts. The Kaplan-Meier median is not reached because fewer than 50\% of contracts experience the selected proxy event before censoring. Survival is {pct(surv_m2.survival_12m)} at 12 months, {pct(surv_m2.survival_24m)} at 24 months, {pct(surv_m2.survival_48m)} at 48 months, and {pct(surv_m2.survival_60m)} at 60 months.

The reduced Cox C-index is {surv_m2.cox_c_index:.3f}; the richer category-aware specification reaches {rich_c_m2:.3f}. PH diagnostics show a strong violation for declared duration (p = {ph_decl.p:.2e}), while imputation status (p = {ph_imp.p:.3f}) and start year (p = {ph_year.p:.3f}) do not show the same violation. This supports using Cox mainly as a diagnostic ranking model and keeping AFT/fixed-horizon indicators central for operations.

The method-comparison output selects LogNormalAFT as the best AFT model with AIC {surv_m2.best_aft_aic:.1f}. The separate M2 AFT refit table also selects LogNormalAFT, with AIC {aft_logn.AIC:.1f}; this small difference is retained in \texttt{{source\_values\_used.csv}} because both values exist in executed outputs.

\begin{{table}}[H]
\centering
\caption{{Survival headline comparison. Survival probabilities come from executed method-survival outputs.}}
\small
\begin{{tabular}}{{lrrrrrrr}}
\toprule
Method & Events & KM median & S12 & S24 & S48 & S60 & Cox C \\
\midrule
M0 balanced & {int(surv_m0.events)} & not reached & {pct(surv_m0.survival_12m)} & {pct(surv_m0.survival_24m)} & {pct(surv_m0.survival_48m)} & {pct(surv_m0.survival_60m)} & {surv_m0.cox_c_index:.3f} \\
M2 balanced & {int(surv_m2.events)} & not reached & {pct(surv_m2.survival_12m)} & {pct(surv_m2.survival_24m)} & {pct(surv_m2.survival_48m)} & {pct(surv_m2.survival_60m)} & {surv_m2.cox_c_index:.3f} \\
M0 strict & {int(surv_strict.events)} & not reached & {pct(surv_strict.survival_12m)} & {pct(surv_strict.survival_24m)} & {pct(surv_strict.survival_48m)} & {pct(surv_strict.survival_60m)} & {surv_strict.cox_c_index:.3f} \\
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{figures/fig_km_method_comparison.png}}
\caption{{Kaplan-Meier comparison for real BOAMP proxy-event definitions. Source: generated from executed survival outputs.}}
\end{{figure}}

\section{{Operational 12/24-Month Indicators}}
The selected survival model is converted into contract-level p12 and p24 scores. These are prioritization scores for identifiable BOAMP proxy recurrences. They can support monitoring lists and segment planning, especially where many small probabilities aggregate into a meaningful buyer or segment workload.

Operational indicators are available for {len(risk):,} contracts. The median 12-month score is {risk.p_renewal_12m.median():.4f}; the median 24-month score is {risk.p_renewal_24m.median():.4f}. Summed across scored contracts, expected proxy recurrences are {risk.p_renewal_12m.sum():.1f} at 12 months and {risk.p_renewal_24m.sum():.1f} at 24 months.

\begin{{table}}[H]
\centering
\caption{{Top buyer-level expected proxy recurrences under M2 balanced. Source: survival model output.}}
\small
\begin{{tabular}}{{lrrr}}
\toprule
Buyer key & Contracts & Expected 12m & Expected 24m \\
\midrule
{top_buyer_rows}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{table}}[H]
\centering
\caption{{Top segment-level expected proxy recurrences under M2 balanced. Source: survival model output.}}
\small
\begin{{tabular}}{{lrrr}}
\toprule
Segment & Contracts & Expected 12m & Expected 24m \\
\midrule
{top_segment_rows}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.72\linewidth]{{figures/fig_m2_risk_distribution.png}}
\caption{{Distribution of 12-month proxy-recurrence prioritization scores under M2 balanced. Source: survival model output.}}
\end{{figure}}

\section{{Robustness and Sensitivity}}
The survival conclusions are stable across M0 balanced and M2 balanced in the current outputs. M0 balanced has {pct(surv_m0.survival_12m)} 12-month survival and {pct(surv_m0.survival_24m)} 24-month survival, while M2 balanced has {pct(surv_m2.survival_12m)} and {pct(surv_m2.survival_24m)}. This supports the applied interpretation that most contracts do not show an identifiable proxy recurrence within the first two years.

M0 strict is mainly a lower-bound sensitivity: it has only {int(strict_row.event_count)} events and {pct(strict_row.event_rate)} event rate. Broad rules are useful to check high-recall behavior but are not selected for the main survival model. M2 has a higher generic-CPV share than M0 balanced ({pct(selected_row.generic_cpv_share)} versus {pct(m0_row.generic_cpv_share)}), so generic-CPV M2 links should be reviewed first in the next manual validation pass.

\section{{Limitations}}
\begin{{longtable}}{{p{{.27\linewidth}}p{{.32\linewidth}}p{{.32\linewidth}}}}
\caption{{Limitations and mitigations.}}\\
\toprule
Limitation & Consequence & Mitigation / current status \\
\midrule
\endfirsthead
\toprule
Limitation & Consequence & Mitigation / current status \\
\midrule
\endhead
{limitations_rows}
\bottomrule
\end{{longtable}}

\section{{Conclusion and Next Steps}}
The project now has a calibrated, traceable proxy-event definition for BOAMP recurrence analysis. The selected main method is M2 balanced; M0 balanced remains the conservative transparent baseline; the old {int(old.event.sum())}-event output is historical pre-calibration only. Survival analysis under the selected method produces readable 12- and 24-month indicators for operational prioritization.

The next work should focus on method-neutral manual review of M2 links, inspection of generic-CPV M2 links, integration of final NLP labels when the separate team classifier is available, Phase 4 trend/change-point analysis, and optional DECP enrichment. Those steps would make the operational layer more robust without changing the central interpretation: BOAMP does not provide legal renewal ground truth, so the analysis must remain explicit about proxy recurrence and diagnostic evidence.

\appendix
\clearpage
\section{{Validation Framework Diagrams}}
\begin{{figure}}[H]
\centering
\includegraphics[width=.9\linewidth]{{figures/fig_no_ground_truth_validation_framework.pdf}}
\caption{{Validation framework in a no-ground-truth BOAMP setting. Source: generated from the executed project pipeline and validation outputs.}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.86\linewidth]{{figures/fig_proxy_event_construction.pdf}}
\caption{{Proxy-event construction diagram for real BOAMP candidate links. Source: generated from the executed project pipeline and validation outputs.}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.9\linewidth]{{figures/fig_m0_m1_m2_method_logic.pdf}}
\caption{{M0/M1/M2 method logic. Source: generated from the executed project pipeline and validation outputs.}}
\end{{figure}}

\section{{Top Contract Indicators}}
\begin{{table}}[H]
\centering
\caption{{Top contract-level p12/p24 scores under M2 balanced. Source: survival model output.}}
\small
\begin{{tabular}}{{llrr}}
\toprule
Contract & Segment & p12 & p24 \\
\midrule
{top_contract_rows}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.82\linewidth]{{figures/fig_top_contracts_m2_balanced.png}}
\caption{{Top contract-level 12/24-month proxy-recurrence scores under M2 balanced. Source: survival model output.}}
\end{{figure}}

\clearpage
\section{{Source Trace Extract}}
The complete trace table is stored in \texttt{{source\_values\_used.csv}}. The extract below shows the main headline values and their executed output sources.

\begin{{longtable}}{{@{{}}p{{.18\linewidth}}p{{.24\linewidth}}p{{.20\linewidth}}p{{.28\linewidth}}@{{}}}}
\caption{{Extract from the source trace table.}}\\
\toprule
Section & Metric & Value & Source file \\
\midrule
\endfirsthead
\toprule
Section & Metric & Value & Source file \\
\midrule
\endhead
selection & selected method & M2 balanced & final recommendation \\
selection & threshold & 0.65 & probabilistic linkage results \\
population & raw BOAMP notices & {counts['raw_notices']:,} & cleaned BOAMP data \\
population & APPEL\_OFFRE notices & {counts['appel_offre']:,} & cleaned BOAMP data \\
population & eligible contracts & {counts['eligible']:,} & M2 balanced survival input \\
population & selected M2 events & {counts['m2_events']:,} & M2 balanced survival input \\
population & selected M2 censored rows & {counts['m2_censored']:,} & M2 balanced survival input \\
historical & pre-calibration events & {int(old.event.sum())} & historical handoff \\
method comparison & M2 synthetic precision/recall/F1 & 0.612 / 0.733 / 0.667 & synthetic metrics \\
method comparison & M2 negative-control acceptance & {pct(selected_row.negative_control_acceptance_rate)} & method comparison \\
survival & M2 survival 12/24/48/60m & {pct(surv_m2.survival_12m)} / {pct(surv_m2.survival_24m)} / {pct(surv_m2.survival_48m)} / {pct(surv_m2.survival_60m)} & method survival comparison \\
survival & reduced Cox C-index & {surv_m2.cox_c_index:.3f} & method survival comparison \\
survival & richer Cox C-index & {rich_c_m2:.3f} & category-aware Cox table \\
survival & best AFT / AIC & LogNormalAFT / {surv_m2.best_aft_aic:.1f} & method survival comparison \\
operational & scored contracts & {len(risk):,} & M2 risk indicators \\
operational & median p12 / p24 & {risk.p_renewal_12m.median():.4f} / {risk.p_renewal_24m.median():.4f} & M2 risk indicators \\
operational & expected 12/24m recurrences & {risk.p_renewal_12m.sum():.1f} / {risk.p_renewal_24m.sum():.1f} & M2 risk indicators \\
\bottomrule
\end{{longtable}}

\clearpage
\section{{Internal References}}
This first draft uses only existing project outputs and method names already present in the repository. The main internal sources are the final method recommendation table, the linkage method comparison tables, the method survival comparison table, the M2 balanced 12/24-month risk table, and the selected M2 balanced survival input. Exact paths are listed in \texttt{{source\_values\_used.csv}}. External literature citations can be added later if the report is expanded into a formal academic manuscript.

\end{{document}}
"""
    (OUT / "gigalis_boamp_proxy_recurrence_survival_report.tex").write_text(tex)

    readme = f"""# Gigalis BOAMP Proxy Recurrence Survival Report

This folder contains a first draft synthesis report for the BOAMP / Gigalis internship project.

## Main files

- `gigalis_boamp_proxy_recurrence_survival_report.tex`: LaTeX source.
- `gigalis_boamp_proxy_recurrence_survival_report.pdf`: rendered report.
- `source_values_used.csv`: trace table for reported numbers.
- `figures/`: generated diagrams plus selected current project figures copied for this draft.

## Current selected method

The selected main method is **{selected}** with match-probability threshold `{prob_m2.threshold}`. The final modeling input is:

`{surv_m2.survival_dataset}`

It contains {counts['eligible']:,} eligible contracts, {counts['m2_events']:,} proxy recurrence events, and {counts['m2_censored']:,} censored rows ({plain_pct(selected_row.event_rate)} event rate).

## Historical results

`data/processed/boamp_phase2_survival.csv` is retained as the historical pre-calibration baseline only. It has {int(old.event.sum()):,} events out of {len(old):,} eligible contracts ({plain_pct(old.event.mean())}).

M0 balanced remains the conservative transparent baseline, with {int(m0_row.event_count):,} proxy events ({plain_pct(m0_row.event_rate)}).

## Rebuild

From the repository root:

```bash
python3 reports/final_draft/build_final_draft.py
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
```

The build script reads only executed project outputs already present in the repository. It does not rerun notebooks.

## Important interpretation

The event variable is a proxy recurrence outcome: an identifiable reappearance of a similar procurement need. It is not a verified legal renewal, and real BOAMP precision/recall are not directly observable.
"""
    (OUT / "README.md").write_text(readme)


if __name__ == "__main__":
    main()
