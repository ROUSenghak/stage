from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import ROOT, append_run_log, utc_now


OUT = ROOT / "reports" / "final_draft"
FIG = OUT / "figures"


def read(rel: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(ROOT / rel, **kwargs)


def pct(value, digits: int = 1) -> str:
    return f"{100 * float(value):.{digits}f}\\%"


def plain_pct(value, digits: int = 1) -> str:
    return f"{100 * float(value):.{digits}f}%"


def esc(value) -> str:
    text = "" if pd.isna(value) else str(value)
    return (
        text.replace("\\", r"\textbackslash{}")
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


def tt(path: str) -> str:
    return r"\protect\path{" + str(path).replace("}", "") + "}"


def add_trace(rows: list[dict], section: str, metric: str, value, source_file: str, column: str, note: str = "") -> None:
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


def box(ax, x, y, w, h, text, fc="#f7f9fb", ec="#536d7a", fs=8.5):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.025",
        linewidth=0.9,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, wrap=True)


def save_diagram(name: str, nodes: list[str], title: str, rows: int) -> None:
    cols = math.ceil(len(nodes) / rows)
    fig, ax = plt.subplots(figsize=(11, 2.2 * rows + 0.6))
    ax.set_axis_off()
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows + 0.2)
    ax.text(0, rows + 0.04, title, fontsize=11, fontweight="bold", va="bottom")
    positions = []
    for i, label in enumerate(nodes):
        row = rows - 1 - (i // cols)
        col = i % cols
        x, y, w, h = col + 0.08, row + 0.25, 0.78, 0.42
        box(ax, x, y, w, h, label)
        positions.append((x, y, w, h))
    for i, (x, y, w, h) in enumerate(positions[:-1]):
        if rows > 1 and (i + 1) % cols == 0:
            continue
        nx, ny, _, nh = positions[i + 1]
        ax.annotate(
            "",
            xy=(nx, ny + nh / 2),
            xytext=(x + w, y + h / 2),
            arrowprops=dict(arrowstyle="->", lw=0.9, color="#536d7a", shrinkA=4, shrinkB=4),
        )
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def method_rows(methods: pd.DataFrame) -> str:
    rows = []
    for r in methods.itertuples(index=False):
        rows.append(
            f"{esc(r.method + ' ' + r.variant)} & {int(r.event_count):,} & {pct(r.event_rate)} & "
            f"{float(r.synthetic_benchmark_precision):.3f} & {float(r.synthetic_benchmark_recall):.3f} & "
            f"{float(r.synthetic_benchmark_f1):.3f} & {pct(r.negative_control_acceptance)} & {pct(r.generic_cpv_share)} \\\\"
        )
    return "\n".join(rows)


def classifier_rows(classifiers: pd.DataFrame) -> str:
    rows = []
    for r in classifiers.itertuples(index=False):
        if str(r.status).startswith("not_run"):
            rows.append(f"{esc(r.model)} & blocked & -- & -- & -- \\\\")
        else:
            rows.append(f"{esc(r.model)} & {esc(r.status)} & {float(r.precision):.3f} & {float(r.recall):.3f} & {float(r.f1):.3f} \\\\")
    return "\n".join(rows)


def ranking_rows(df: pd.DataFrame, kind: str, n: int = 8) -> str:
    rows = []
    for r in df.head(n).itertuples(index=False):
        if kind == "buyer":
            rows.append(
                f"{esc(r.buyer_key)} & {esc(r.buyer_name)} & {int(r.n_contracts):,} & "
                f"{float(r.expected_renewals_12m):.2f} & {float(r.expected_renewals_24m):.2f} \\\\"
            )
        elif kind == "segment":
            rows.append(
                f"{esc(r.segment)} & {int(r.n_contracts):,} & "
                f"{float(r.expected_renewals_12m):.2f} & {float(r.expected_renewals_24m):.2f} & {float(r.mean_p12):.3f} \\\\"
            )
        else:
            rows.append(
                f"{esc(r.contract_id)} & {esc(r.buyer_name)} & {esc(r.segment)} & "
                f"{float(r.p_renewal_12m):.3f} & {float(r.p_renewal_24m):.3f} \\\\"
            )
    return "\n".join(rows)


def build_tex(values: dict, final_draft: bool, nested_report: bool = False) -> str:
    if final_draft:
        cur = "../figures"
        diag = "figures"
    elif nested_report:
        cur = "../figures"
        diag = "../final_draft/figures"
    else:
        cur = "figures"
        diag = "final_draft/figures"
    title = (
        "From Current BOAMP Notices to Procurement-Recurrence Risk:"
        r"\\A Current Enriched Proxy-Event and Survival-Analysis Framework for Gigalis"
    )
    return rf"""
\documentclass[11pt,a4paper]{{article}}
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
\title{{{title}}}
\author{{Gigalis internship project}}
\date{{Generated from current executed outputs on {utc_now()}}}

\begin{{document}}
\maketitle

\begin{{abstract}}
This report replaces the earlier 2015--2024 synthesis with a current enriched BOAMP study. It keeps the rich methodological structure of the previous draft, but every headline number is rebuilt from the current files under {tt('data/processed/boamp_current/')} and current report tables. The event is a proxy recurrence, meaning an identifiable reappearance of a similar procurement need in BOAMP; it is not a legally verified renewal.
\end{{abstract}}

\tableofcontents
\clearpage

\section{{Executive Summary}}
Gigalis needs a practical way to monitor public digital procurement needs before they reappear in BOAMP. The current enriched dataset covers {values['actual_range']} and contains {values['retained']:,} retained BOAMP notices. Within that source, {values['appel']:,} are APPEL\_OFFRE notices. After start-date and duration eligibility rules, {values['eligible']:,} contracts are eligible for recurrence linkage.

The current selected event definition is \textbf{{{esc(values['selected_method'])}}}. It produces {values['events']:,} proxy recurrence events and {values['censored']:,} censored contracts, an event rate of {pct(values['event_rate'])}. M2 balanced has the strongest current synthetic/silver F1 ({values['m2_f1']:.3f}) and very high precision, but it keeps only {values['m2_events']:,} events. The current selection therefore keeps M0 balanced as the main operational survival definition because it has enough events for survival modeling, transparent thresholds, zero current negative-control acceptance, and stable interpretation.

Under the selected definition, Kaplan--Meier survival is {pct(values['s12'])} at 12 months, {pct(values['s24'])} at 24 months, {pct(values['s48'])} at 48 months, and {pct(values['s60'])} at 60 months. The current Cox model has C-index {values['cox_c']:.3f}; the selected AFT model is {esc(values['aft_model'])} with AIC {values['aft_aic']:.1f}. The live scoring table covers {values['risk_rows']:,} contracts and gives mean p12/p24 of {values['mean_p12']:.3f}/{values['mean_p24']:.3f}, corresponding to {values['exp12']:.1f} expected proxy recurrences within 12 months and {values['exp24']:.1f} within 24 months.

\section{{Business Context and Interpretation}}
The study supports account monitoring and segment planning. It does not try to prove a legal renewal chain. BOAMP does not contain a complete contract-history identifier linking each call for tender to later renewals. The output is therefore a prioritization layer: it identifies plausible, observable reappearances of similar digital procurement needs.

The distinction matters operationally. A high p12 or p24 score means that under the selected proxy-event definition and fitted survival model, a similar BOAMP notice is relatively likely to be observed soon. It does not mean that the buyer has a legal obligation to renew, that an incumbent contract will be extended, or that a future notice is guaranteed.

\section{{Current Data Source and Study Period}}
The downloader used the BOAMP Opendatasoft API, Pays de la Loire departments, and digital CPV divisions. It requested 2015-01-01 to 2026-07-09 and retained a verified actual date range of {values['actual_range']}. Raw JSON pages and metadata are cached under {tt('data/raw/boamp_current/')} and the flattened current source is {tt('data/processed/boamp_current/boamp_full_flat.csv')}.

\begin{{table}}[H]
\centering
\caption{{Current analytical population funnel. Source: {tt('reports/tables/data/analytical_population_summary.csv')}.}}
\begin{{tabular}}{{lrl}}
\toprule
Stage & Rows & Interpretation \\
\midrule
All current notices & {values['retained']:,} & downloaded and deduplicated BOAMP notices \\
APPEL\_OFFRE notices & {values['appel']:,} & survival source unit \\
APPEL\_OFFRE with valid source date & {values['valid_source']:,} & usable start date before censoring \\
Eligible for linkage & {values['eligible']:,} & expected end date plus search buffer before censoring \\
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.82\linewidth]{{{cur}/data/analytical_population_funnel.pdf}}
\caption{{Current analytical population funnel generated from the refreshed pipeline.}}
\end{{figure}}

\section{{SIREN/SIRET Enrichment and Buyer-Key Construction}}
The current cleaning pipeline preserves raw buyer names and raw identifiers, then builds cleaned SIRET, cleaned SIREN, SIREN extracted from SIRET, and high-confidence enriched SIREN when possible. The buyer key is assigned in this order: valid SIRET, valid SIREN, SIREN extracted from SIRET, enriched SIREN, and finally normalized-name fallback.

The refreshed dataset has {values['valid_siret']:,} rows with valid SIRET and {values['enriched_siren']:,} rows with enriched SIREN. Buyer-key quality is central because it controls the blocking step: better buyer grouping increases the chance of finding plausible later notices without opening the candidate pool to unrelated buyers.

\begin{{table}}[H]
\centering
\caption{{Buyer-key distribution in the current enriched dataset. Source: {tt('reports/tables/data/buyer_key_quality_summary.csv')}.}}
\begin{{tabular}}{{lrr}}
\toprule
Buyer key type & Rows & Distinct buyer keys \\
\midrule
{values['buyer_quality_rows']}
\bottomrule
\end{{tabular}}
\end{{table}}

\section{{Cleaning, Duration, CPV, and Traceability}}
The current dataset normalizes notice identifiers, publication dates, nature, buyer names, SIRET/SIREN, CPV, procurement-object text, duration, and source-date fields. CPV is converted into a cleaned code, hierarchy fields, and generic-CPV flags. Generic codes are treated cautiously because a broad code can make two notices look more similar than they really are. Duration is preserved when plausible and imputed when missing or suspect; the imputation flag remains available downstream so survival models can account for this uncertainty.

Traceability is kept at every stage: raw notice IDs and raw-record fields are preserved in the enriched table, candidate-pair files keep both source and candidate identifiers, selected event datasets keep the method definition, and report values are traced in {tt('reports/current_source_values_used.csv')} and {tt('reports/final_draft/source_values_used.csv')}.

\section{{Candidate-Pair Generation}}
Candidate pairs are generated within the enriched buyer key. A source APPEL\_OFFRE can link only to a later notice from the same buyer key, and the search window is centered around the expected end date. The candidate table includes text similarity, CPV compatibility, temporal proximity, buyer-key quality, generic-CPV flags, duration features, candidate rank, score margin, and the text backend. The refreshed run used {esc(values['text_backend'])}.

\begin{{table}}[H]
\centering
\caption{{Current candidate generation summary. Source: {tt('reports/tables/linkage/candidate_generation_summary.csv')}.}}
\begin{{tabular}}{{lr}}
\toprule
Metric & Value \\
\midrule
Eligible source contracts & {values['eligible']:,} \\
Candidate pairs & {values['candidate_pairs']:,} \\
Sources with at least one candidate & {values['sources_with_candidate']:,} \\
Text similarity backend & {esc(values['text_backend'])} \\
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{{cur}/linkage/candidate_count_distribution.pdf}}
\caption{{Distribution of candidate counts per eligible source contract.}}
\end{{figure}}

\section{{No-Ground-Truth Validation Framework}}
Real BOAMP does not provide true recurrence-chain labels. This study therefore uses several imperfect but complementary diagnostics:
\begin{{enumerate}}
\item synthetic/silver labels to estimate precision, recall, and F1 under controlled conditions;
\item negative-control acceptance to detect implausible false-positive behavior;
\item external-reference diagnostics such as ATTRIBUTION {tt('annonce_lie')} only as weak signals;
\item subgroup audits for generic CPV, name-fallback buyers, imputed durations, near-threshold links, and low-margin links;
\item unique-link diagnostics to identify candidate notices reused too often.
\end{{enumerate}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.92\linewidth]{{{diag}/fig_no_ground_truth_validation_framework.pdf}}
\caption{{Validation logic for BOAMP recurrence when real legal renewal ground truth is unavailable.}}
\end{{figure}}

\section{{M0, M1, and M2 Linkage Methods}}
M0 is the deterministic composite-rule family. It is transparent and easy to audit: the selected balanced variant applies text, composite score, margin, and generic-CPV logic directly. M1 is a probabilistic classifier over the current pair features. M2 is the probability/review-zone variant: it performs very well on synthetic/silver labels but is intentionally stricter in the current data.

\begin{{table}}[H]
\centering
\caption{{Current M0/M1/M2 method comparison. Synthetic/silver metrics are diagnostics, not real BOAMP truth.}}
\small
\resizebox{{\linewidth}}{{!}}{{%
\begin{{tabular}}{{lrrrrrrr}}
\toprule
Method & Events & Event rate & Precision & Recall & F1 & Neg. control & Generic CPV \\
\midrule
{values['method_rows']}
\bottomrule
\end{{tabular}}
}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{{cur}/linkage/method_event_counts.pdf}}
\caption{{Current proxy recurrence event counts by method.}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{{cur}/linkage/method_score_distributions.pdf}}
\caption{{Current score/probability distributions by method.}}
\end{{figure}}

\section{{Methodology Tests Inspired by Record Linkage Literature}}
The refreshed methodology tables test classifier alternatives, blocking alternatives, text-similarity alternatives, threshold zones, active-learning label budgets, subgroup quality, unique-link reuse, and weak external references. The classifier benchmark does not treat BOAMP as ground truth; it uses current synthetic/silver labels and real-data diagnostics.

\begin{{table}}[H]
\centering
\caption{{Current classifier benchmark. LightGBM is blocked by a missing system OpenMP library and is not used as selection evidence.}}
\small
\begin{{tabular}}{{llrrr}}
\toprule
Model & Status & Precision & Recall & F1 \\
\midrule
{values['classifier_rows']}
\bottomrule
\end{{tabular}}
\end{{table}}

Threshold-zone diagnostics are retained for review prioritization rather than replacing the final event definition. The current possible-match zone contains {values['possible_zone']:,} candidate pairs and the strong-match zone contains {values['strong_zone']:,}; this distinction is useful for future manual review queues.

\section{{Final Selected Proxy-Event Definition}}
The selected current event definition is \textbf{{{esc(values['selected_method'])}}}. It is not selected because it maximizes benchmark F1. It is selected because the current study needs a survival-ready event definition that balances event sufficiency, interpretability, negative-control behavior, generic-CPV risk, and operational stability.

M2 balanced is important evidence, not the selected survival input. It has F1 {values['m2_f1']:.3f}, precision {values['m2_precision']:.3f}, recall {values['m2_recall']:.3f}, zero generic-CPV share, and {values['m2_events']:,} events. That is excellent as a strong-match / review-priority layer, but too sparse to replace the selected event definition in the current survival study without making the event count fragile. The selected M0 balanced definition keeps {values['events']:,} events, zero current negative-control acceptance, and readable rule logic.

\section{{Survival-Analysis Methodology}}
The survival unit remains APPEL\_OFFRE. Each eligible source contract receives an observed duration: either time to selected proxy recurrence, or time to censoring if no selected proxy recurrence is observed. Kaplan--Meier estimates the nonparametric survival curve. Cox PH is used as a ranking and covariate diagnostic. AFT models compare parametric time-to-event shapes and provide the operational p12/p24 scoring layer.

\begin{{figure}}[H]
\centering
\includegraphics[width=.9\linewidth]{{{diag}/fig_survival_modeling_workflow.pdf}}
\caption{{Current survival modeling workflow from selected proxy-event definition to operational p12/p24 indicators.}}
\end{{figure}}

\section{{Current Survival Results}}
Under {esc(values['selected_method'])}, there are {values['events']:,} proxy recurrence events among {values['eligible']:,} eligible contracts. The Kaplan--Meier median is not reached, because fewer than half of contracts experience the selected proxy recurrence before censoring. Survival remains high at the first operational horizons: {pct(values['s12'])} at 12 months and {pct(values['s24'])} at 24 months.

\begin{{table}}[H]
\centering
\caption{{Current survival headline results. Source: {tt('reports/tables/survival/survival_summary_current.csv')}.}}
\begin{{tabular}}{{lrrrrr}}
\toprule
Method & Events & Event rate & S12 & S24 & S60 \\
\midrule
{esc(values['selected_method'])} & {values['events']:,} & {pct(values['event_rate'])} & {pct(values['s12'])} & {pct(values['s24'])} & {pct(values['s60'])} \\
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{{cur}/survival/km_curve_current.pdf}}
\caption{{Kaplan--Meier curve under the selected current proxy-event definition.}}
\end{{figure}}

\section{{Cox and AFT Model Diagnostics}}
The current Cox model C-index is {values['cox_c']:.3f}. Duration has a negative coefficient, meaning longer declared duration is associated with lower short-term recurrence hazard in the fitted model. Buyer-key type and segment terms are retained as diagnostics, not causal effects.

\begin{{table}}[H]
\centering
\caption{{Selected Cox coefficients. Source: {tt('reports/tables/survival/cox_results_current.csv')}.}}
\small
\begin{{tabular}}{{lrrr}}
\toprule
Variable & Coef. & Hazard ratio & p-value \\
\midrule
{values['cox_rows']}
\bottomrule
\end{{tabular}}
\end{{table}}

The selected AFT model is {esc(values['aft_model'])}. The AFT comparison is useful because fixed-horizon operational probabilities require a full predicted survival curve, not only a relative hazard ranking.

\begin{{table}}[H]
\centering
\caption{{Current AFT model comparison. Source: {tt('reports/tables/survival/aft_comparison_current.csv')}.}}
\begin{{tabular}}{{lrr}}
\toprule
Model & AIC & Events \\
\midrule
{values['aft_rows']}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{{cur}/survival/aft_model_comparison_current.pdf}}
\caption{{AFT comparison under the selected current event definition.}}
\end{{figure}}

\section{{Operational 12/24-Month Indicators}}
The operational layer scores contracts by conditional p12 and p24 under the selected AFT model. These are prioritization scores for visible BOAMP proxy recurrences. Mean p12 is {values['mean_p12']:.3f}, mean p24 is {values['mean_p24']:.3f}, and the expected current workload is {values['exp12']:.1f} proxy recurrences in 12 months and {values['exp24']:.1f} in 24 months.

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{{cur}/survival/p12_distribution_current.pdf}}
\caption{{Distribution of current 12-month proxy-recurrence probabilities.}}
\end{{figure}}

\begin{{table}}[H]
\centering
\caption{{Top buyer-level expected proxy recurrences. Source: {tt('reports/tables/survival/buyer_risk_ranking_current.csv')}.}}
\small
\begin{{tabular}}{{llrrr}}
\toprule
Buyer key & Buyer name & Contracts & Expected 12m & Expected 24m \\
\midrule
{values['buyer_rows']}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{table}}[H]
\centering
\caption{{Top segment-level expected proxy recurrences. Source: {tt('reports/tables/survival/segment_risk_ranking_current.csv')}.}}
\small
\begin{{tabular}}{{lrrrr}}
\toprule
Segment & Contracts & Expected 12m & Expected 24m & Mean p12 \\
\midrule
{values['segment_rows']}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{table}}[H]
\centering
\caption{{Top contract-level p12/p24 scores. Source: {tt('reports/tables/survival/contract_risk_ranking_current.csv')}.}}
\small
\begin{{tabular}}{{lllrr}}
\toprule
Contract & Buyer & Segment & p12 & p24 \\
\midrule
{values['contract_rows']}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.76\linewidth]{{{cur}/survival/top_buyer_risk_current.pdf}}
\caption{{Top buyer-level expected 12-month proxy recurrence workload.}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.76\linewidth]{{{cur}/survival/top_segment_risk_current.pdf}}
\caption{{Top segment-level expected 12-month proxy recurrence workload.}}
\end{{figure}}

\section{{Robustness, Review Priorities, and Remaining Risks}}
The main review priorities are generic CPV links, name-fallback buyer keys, imputed durations, near-threshold links, low-margin links, and large buyers. Unique-link diagnostics show that some candidate notices are reused many times, with the top reused candidate appearing {values['top_reuse']} times. This does not invalidate the method, but it marks those cases for manual review because one later framework-style notice can plausibly be similar to several earlier needs.

\begin{{longtable}}{{p{{.28\linewidth}}p{{.31\linewidth}}p{{.31\linewidth}}}}
\caption{{Current limitations and mitigations.}}\\
\toprule
Limitation & Consequence & Mitigation / current status \\
\midrule
\endfirsthead
\toprule
Limitation & Consequence & Mitigation / current status \\
\midrule
\endhead
No BOAMP legal renewal labels & Real precision and recall are not directly observable & Use proxy wording, synthetic/silver benchmark, negative controls, and review queues \\
M2 is sparse & Strong-match F1 is high but event count is only {values['m2_events']:,} & Keep M2 as review/strong-match evidence; select M0 balanced for current survival \\
Generic CPV ambiguity & Broad CPV codes can create weak semantic evidence & Flag generic CPV and audit those links first \\
Name-fallback buyers & Residual buyer fragmentation and false grouping risk remain & Continue SIREN/SIRET enrichment and manual buyer checks \\
Duration imputation & Timing uncertainty can affect expected end dates & Preserve duration-imputation flags in linkage and survival outputs \\
LightGBM blocked & One optional classifier benchmark cannot run & Record missing {tt('libgomp.so.1')} and exclude LightGBM from selection evidence \\
External references are weak & ATTRIBUTION {tt('annonce_lie')} is not complete ground truth & Use only as diagnostic support, not a label source \\
\bottomrule
\end{{longtable}}

\section{{Conclusion and Next Steps}}
The current enriched BOAMP dataset is now the source of truth for this study. The rich report no longer compares old and new results as a main objective. It documents the current data, current enrichment, current linkage, current selected proxy-event definition, current survival outputs, and current operational prioritization layer.

The next substantive work should be method-neutral manual review of possible-match and strong-match zones, targeted review of name-fallback and generic-CPV links, installation or environment support for LightGBM if that benchmark remains desired, and incorporation of reviewed labels into an active-learning loop. The central interpretation should stay conservative: this is a proxy recurrence framework for public BOAMP observability, not a legal renewal detector.

\appendix
\clearpage
\section{{Pipeline and Source Trace}}
\begin{{figure}}[H]
\centering
\includegraphics[width=.95\linewidth]{{{diag}/fig_pipeline_overview.pdf}}
\caption{{Current rich-study pipeline from BOAMP download to operational scoring.}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.9\linewidth]{{{diag}/fig_proxy_event_construction.pdf}}
\caption{{Current proxy-event construction logic.}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.9\linewidth]{{{diag}/fig_m0_m1_m2_method_logic.pdf}}
\caption{{Current M0/M1/M2 method roles.}}
\end{{figure}}

The complete source trace is stored in {tt('reports/current_source_values_used.csv')} and {tt('reports/final_draft/source_values_used.csv')}. The active current report table, figure, notebook, and audit outputs were regenerated after the live BOAMP API download.

\end{{document}}
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    download = read("reports/tables/data/boamp_current_download_summary.csv")
    enrich = read("reports/tables/data/buyer_enrichment_summary.csv")
    buyer_quality = read("reports/tables/data/buyer_key_quality_summary.csv")
    pop = read("reports/tables/data/analytical_population_summary.csv")
    cand_summary = read("reports/tables/linkage/candidate_generation_summary.csv")
    methods = read("reports/tables/linkage/method_comparison_current_dataset.csv")
    selected = read("reports/tables/linkage/final_selected_event_definition_current.csv").iloc[0]
    surv = read("reports/tables/survival/survival_summary_current.csv").iloc[0]
    cox = read("reports/tables/survival/cox_results_current.csv")
    aft = read("reports/tables/survival/aft_comparison_current.csv")
    risk = read("reports/tables/survival/operational_risk_scores_current.csv")
    buyers = read("reports/tables/survival/buyer_risk_ranking_current.csv")
    segments = read("reports/tables/survival/segment_risk_ranking_current.csv")
    contracts = read("reports/tables/survival/contract_risk_ranking_current.csv", dtype={"SIREN": str, "SIRET": str})
    classifiers = read("reports/tables/validation/classifier_benchmark_current.csv")
    zones = read("reports/tables/validation/threshold_zone_analysis_current.csv")
    unique = read("reports/tables/validation/unique_link_constraint_diagnostics_current.csv")

    actual_range = str(download["actual_date_range"].dropna().iloc[-1])
    retained = int(download["number_of_retained_notices"].dropna().iloc[-1])
    raw = int(download["number_of_raw_notices"].dropna().iloc[-1])
    appel = int(enrich.loc[enrich["metric"].eq("APPEL_OFFRE"), "value"].iloc[0])
    valid_siret = int(enrich.loc[enrich["metric"].eq("valid_siret_rows"), "value"].iloc[0])
    enriched_siren = int(enrich.loc[enrich["metric"].eq("enriched_siren_rows"), "value"].iloc[0])
    valid_source = int(pop.loc[pop["stage"].eq("appel_offre_with_valid_source_date"), "rows"].iloc[0])
    eligible = int(selected.eligible_contracts)
    events = int(selected.event_count)
    event_rate = float(selected.event_rate)
    censored = eligible - events
    selected_method = f"{selected.selected_method} {selected.selected_variant}"
    m2 = methods[(methods["method"].eq("M2")) & (methods["variant"].eq("balanced"))].iloc[0]
    candidate_pairs = int(cand_summary.loc[cand_summary["metric"].eq("candidate_pairs"), "value"].iloc[0])
    sources_with_candidate = int(cand_summary.loc[cand_summary["metric"].eq("sources_with_candidate"), "value"].iloc[0])
    text_backend = str(cand_summary.loc[cand_summary["metric"].eq("text_similarity_backend"), "value"].iloc[0])
    aft_best = aft.sort_values("AIC").iloc[0]
    cox_c = float(cox["c_index"].dropna().iloc[0])

    save_diagram(
        "fig_pipeline_overview",
        [
            "Live BOAMP API download",
            "Raw JSON cache and metadata",
            "Current cleaning and SIREN/SIRET enrichment",
            "Eligible APPEL_OFFRE population",
            "Enriched buyer-key blocking",
            "Candidate-pair scoring",
            "M0/M1/M2 diagnostics",
            "Selected M0 balanced proxy event",
            "Survival and p12/p24 scoring",
        ],
        "Current enriched BOAMP pipeline",
        rows=3,
    )
    save_diagram(
        "fig_proxy_event_construction",
        [
            "Source APPEL_OFFRE",
            "Declared or imputed duration",
            "Expected end date",
            "Later same buyer-key notices",
            "Text, CPV, timing, margin features",
            "Method threshold",
            "Proxy recurrence or censoring",
        ],
        "Current proxy-event construction",
        rows=2,
    )
    save_diagram(
        "fig_no_ground_truth_validation_framework",
        [
            "No legal renewal labels in BOAMP",
            "Synthetic/silver diagnostics",
            "Negative controls",
            "Weak external references",
            "Subgroup and reuse audits",
            "Method-neutral review queue",
        ],
        "Validation without real BOAMP ground truth",
        rows=2,
    )
    save_diagram(
        "fig_m0_m1_m2_method_logic",
        [
            "M0: transparent composite rules",
            "M1: classifier probability",
            "M2: strong-match/review probability",
            "M0 balanced selected for survival sufficiency",
            "M2 retained as high-confidence diagnostic",
        ],
        "Current M0/M1/M2 method roles",
        rows=1,
    )
    save_diagram(
        "fig_survival_modeling_workflow",
        [
            "Selected proxy event",
            "Event/censoring duration",
            "Kaplan-Meier",
            "Cox diagnostics",
            "AFT comparison",
            "Live p12/p24 indicators",
        ],
        "Current survival modeling workflow",
        rows=2,
    )

    buyer_quality_rows = "\n".join(
        f"{esc(r.buyer_key_type)} & {int(r.rows):,} & {int(r.buyers):,} \\\\"
        for r in buyer_quality.itertuples(index=False)
    )
    cox_rows = "\n".join(
        f"{esc(r['variable'])} & {float(r['coef']):.3f} & {float(r['exp(coef)']):.3f} & {float(r['p']):.3g} \\\\"
        for _, r in cox.head(8).iterrows()
    )
    aft_rows = "\n".join(f"{esc(r.model)} & {float(r.AIC):.1f} & {int(r.events):,} \\\\" for r in aft.itertuples(index=False))
    possible_zone = int(zones.loc[zones["threshold_zone"].eq("possible_match_zone"), "candidate_pairs"].iloc[0])
    strong_zone = int(zones.loc[zones["threshold_zone"].eq("strong_match_zone"), "candidate_pairs"].iloc[0])

    values = {
        "actual_range": actual_range,
        "raw": raw,
        "retained": retained,
        "appel": appel,
        "valid_source": valid_source,
        "eligible": eligible,
        "events": events,
        "censored": censored,
        "event_rate": event_rate,
        "selected_method": selected_method,
        "m2_events": int(m2.event_count),
        "m2_precision": float(m2.synthetic_benchmark_precision),
        "m2_recall": float(m2.synthetic_benchmark_recall),
        "m2_f1": float(m2.synthetic_benchmark_f1),
        "s12": float(surv.survival_12m),
        "s24": float(surv.survival_24m),
        "s48": float(surv.survival_48m),
        "s60": float(surv.survival_60m),
        "cox_c": cox_c,
        "aft_model": str(aft_best.model),
        "aft_aic": float(aft_best.AIC),
        "risk_rows": len(risk),
        "mean_p12": float(risk["p_renewal_12m"].mean()),
        "mean_p24": float(risk["p_renewal_24m"].mean()),
        "exp12": float(risk["p_renewal_12m"].sum()),
        "exp24": float(risk["p_renewal_24m"].sum()),
        "valid_siret": valid_siret,
        "enriched_siren": enriched_siren,
        "buyer_quality_rows": buyer_quality_rows,
        "candidate_pairs": candidate_pairs,
        "sources_with_candidate": sources_with_candidate,
        "text_backend": text_backend,
        "method_rows": method_rows(methods),
        "classifier_rows": classifier_rows(classifiers),
        "possible_zone": possible_zone,
        "strong_zone": strong_zone,
        "cox_rows": cox_rows,
        "aft_rows": aft_rows,
        "buyer_rows": ranking_rows(buyers, "buyer"),
        "segment_rows": ranking_rows(segments, "segment"),
        "contract_rows": ranking_rows(contracts, "contract", n=10),
        "top_reuse": int(unique["times_reused"].max()),
    }

    trace = []
    add_trace(trace, "data", "actual_date_range", actual_range, "reports/tables/data/boamp_current_download_summary.csv", "actual_date_range")
    add_trace(trace, "data", "raw_notice_count", raw, "reports/tables/data/boamp_current_download_summary.csv", "number_of_raw_notices")
    add_trace(trace, "data", "retained_notice_count", retained, "reports/tables/data/boamp_current_download_summary.csv", "number_of_retained_notices")
    add_trace(trace, "data", "APPEL_OFFRE_count", appel, "reports/tables/data/buyer_enrichment_summary.csv", "value")
    add_trace(trace, "enrichment", "valid_siret_rows", valid_siret, "reports/tables/data/buyer_enrichment_summary.csv", "value")
    add_trace(trace, "enrichment", "enriched_siren_rows", enriched_siren, "reports/tables/data/buyer_enrichment_summary.csv", "value")
    add_trace(trace, "linkage", "candidate_pairs", candidate_pairs, "reports/tables/linkage/candidate_generation_summary.csv", "value")
    add_trace(trace, "linkage", "selected_method", selected_method, "reports/tables/linkage/final_selected_event_definition_current.csv", "selected_method, selected_variant")
    add_trace(trace, "linkage", "eligible_contracts", eligible, "reports/tables/linkage/final_selected_event_definition_current.csv", "eligible_contracts")
    add_trace(trace, "linkage", "proxy_recurrence_events", events, "reports/tables/linkage/final_selected_event_definition_current.csv", "event_count")
    add_trace(trace, "linkage", "event_rate", plain_pct(event_rate), "reports/tables/linkage/final_selected_event_definition_current.csv", "event_rate")
    add_trace(trace, "linkage", "M2_balanced_F1", f"{float(m2.synthetic_benchmark_f1):.3f}", "reports/tables/linkage/method_comparison_current_dataset.csv", "synthetic_benchmark_f1")
    add_trace(trace, "survival", "survival_12m", plain_pct(surv.survival_12m), "reports/tables/survival/survival_summary_current.csv", "survival_12m")
    add_trace(trace, "survival", "survival_24m", plain_pct(surv.survival_24m), "reports/tables/survival/survival_summary_current.csv", "survival_24m")
    add_trace(trace, "survival", "survival_60m", plain_pct(surv.survival_60m), "reports/tables/survival/survival_summary_current.csv", "survival_60m")
    add_trace(trace, "survival", "cox_c_index", f"{cox_c:.3f}", "reports/tables/survival/cox_results_current.csv", "c_index")
    add_trace(trace, "survival", "selected_AFT", aft_best.model, "reports/tables/survival/aft_comparison_current.csv", "model")
    add_trace(trace, "operational", "mean_p12", f"{values['mean_p12']:.4f}", "reports/tables/survival/operational_risk_scores_current.csv", "p_renewal_12m")
    add_trace(trace, "operational", "mean_p24", f"{values['mean_p24']:.4f}", "reports/tables/survival/operational_risk_scores_current.csv", "p_renewal_24m")
    add_trace(trace, "operational", "expected_12m", f"{values['exp12']:.1f}", "reports/tables/survival/operational_risk_scores_current.csv", "sum(p_renewal_12m)")
    add_trace(trace, "operational", "expected_24m", f"{values['exp24']:.1f}", "reports/tables/survival/operational_risk_scores_current.csv", "sum(p_renewal_24m)")
    add_trace(trace, "limitation", "lightgbm_status", classifiers.loc[classifiers["model"].eq("lightgbm"), "status"].iloc[0], "reports/tables/validation/classifier_benchmark_current.csv", "status")
    trace_df = pd.DataFrame(trace)
    trace_df.to_csv(ROOT / "reports" / "current_source_values_used.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    trace_df.to_csv(OUT / "source_values_used.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    final_tex = build_tex(values, final_draft=True)
    current_tex = build_tex(values, final_draft=False)
    nested_tex = build_tex(values, final_draft=False, nested_report=True)
    (OUT / "gigalis_boamp_proxy_recurrence_survival_report.tex").write_text(final_tex, encoding="utf-8")
    (ROOT / "reports" / "current_boamp_recurrence_study_report.tex").write_text(current_tex, encoding="utf-8")
    (ROOT / "reports" / "phase1_technical_report.tex").write_text(current_tex, encoding="utf-8")
    (ROOT / "reports" / "internship_report.tex").write_text(current_tex, encoding="utf-8")
    (ROOT / "reports" / "datasets_documentation.tex").write_text(current_tex, encoding="utf-8")
    (ROOT / "reports" / "data_quality_report" / "data_quality_report.tex").write_text(nested_tex, encoding="utf-8")
    readme = f"""# Current Rich BOAMP Recurrence Study Report

This folder contains the rich current synthesis report rebuilt from the current enriched BOAMP dataset.

- Main PDF: `gigalis_boamp_proxy_recurrence_survival_report.pdf`
- Main TeX: `gigalis_boamp_proxy_recurrence_survival_report.tex`
- Source trace: `source_values_used.csv`
- Figures: `figures/`

Current selected method: **{selected_method}**.
Current study period: **{actual_range}**.
Eligible contracts: **{eligible:,}**.
Proxy recurrence events: **{events:,}**.

The event is a proxy recurrence, not a legally verified renewal.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    append_run_log(
        [
            "",
            f"## Rich current report rebuild - {utc_now()}",
            "- Replaced shortened wrapper-style final report with a rich current synthesis.",
            "- Wrote reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex",
            "- Wrote reports/current_boamp_recurrence_study_report.tex",
            "- Wrote reports/phase1_technical_report.tex",
            "- Wrote reports/internship_report.tex",
            "- Wrote reports/datasets_documentation.tex",
            "- Wrote reports/data_quality_report/data_quality_report.tex",
            "- Updated current and final_draft source traces.",
        ]
    )
    print("Wrote rich current reports and source traces.")


if __name__ == "__main__":
    main()
