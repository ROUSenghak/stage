from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import ROOT, TABLES_DATA, TABLES_LINKAGE, TABLES_SURVIVAL, TABLES_VALIDATION, append_run_log, ensure_dirs, utc_now


def scalar(df: pd.DataFrame, metric: str, value_col: str = "value"):
    row = df[df.iloc[:, 0].astype(str).eq(metric)]
    return row[value_col].iloc[0] if not row.empty and value_col in row.columns else ""


def add_trace(rows: list[dict], section: str, metric: str, value, source_file: str, source_column_or_table: str, note: str = "") -> None:
    rows.append(
        {
            "section": section,
            "metric": metric,
            "value": value,
            "source_file": source_file,
            "source_column_or_table": source_column_or_table,
            "note": note,
        }
    )


def pct(x) -> str:
    try:
        return f"{100 * float(x):.1f}\\%"
    except Exception:
        return "NA"


def main() -> None:
    ensure_dirs()
    download = pd.read_csv(TABLES_DATA / "boamp_current_download_summary.csv")
    enrich = pd.read_csv(TABLES_DATA / "buyer_enrichment_summary.csv")
    pop = pd.read_csv(TABLES_DATA / "analytical_population_summary.csv")
    selected = pd.read_csv(TABLES_LINKAGE / "final_selected_event_definition_current.csv")
    surv = pd.read_csv(TABLES_SURVIVAL / "survival_summary_current.csv")
    risk = pd.read_csv(TABLES_SURVIVAL / "operational_risk_scores_current.csv")
    methods = pd.read_csv(TABLES_LINKAGE / "method_comparison_current_dataset.csv")
    methodology = pd.read_csv(TABLES_VALIDATION / "methodology_tests_summary_current.csv")
    classifiers = pd.read_csv(TABLES_VALIDATION / "classifier_benchmark_current.csv")

    raw_count = int(download["number_of_raw_notices"].dropna().iloc[-1])
    retained_count = int(download["number_of_retained_notices"].dropna().iloc[-1])
    actual_range = str(download["actual_date_range"].dropna().iloc[-1])
    ao_count = int(scalar(enrich, "APPEL_OFFRE"))
    valid_siret = int(scalar(enrich, "valid_siret_rows"))
    enriched_siren = int(scalar(enrich, "enriched_siren_rows"))
    eligible = int(selected["eligible_contracts"].iloc[0])
    events = int(selected["event_count"].iloc[0])
    event_rate = float(selected["event_rate"].iloc[0])
    selected_method = f"{selected['selected_method'].iloc[0]} {selected['selected_variant'].iloc[0]}"
    censoring = selected["censoring_date"].iloc[0]
    survival_24 = float(surv["survival_24m"].iloc[0])
    survival_60 = float(surv["survival_60m"].iloc[0])
    p12_mean = float(risk["p_renewal_12m"].mean())
    p24_mean = float(risk["p_renewal_24m"].mean())
    exp12 = float(risk["p_renewal_12m"].sum())
    exp24 = float(risk["p_renewal_24m"].sum())
    lightgbm_status = str(classifiers.loc[classifiers["model"].eq("lightgbm"), "status"].iloc[0]) if classifiers["model"].eq("lightgbm").any() else "not_available"

    trace = []
    add_trace(trace, "Current data source and study period", "actual_date_range", actual_range, "reports/tables/data/boamp_current_download_summary.csv", "actual_date_range")
    add_trace(trace, "Current data source and study period", "raw_notice_count", raw_count, "reports/tables/data/boamp_current_download_summary.csv", "number_of_raw_notices")
    add_trace(trace, "Current data source and study period", "retained_notice_count", retained_count, "reports/tables/data/boamp_current_download_summary.csv", "number_of_retained_notices")
    add_trace(trace, "SIREN/SIRET enrichment", "valid_siret_rows", valid_siret, "reports/tables/data/buyer_enrichment_summary.csv", "value")
    add_trace(trace, "SIREN/SIRET enrichment", "enriched_siren_rows", enriched_siren, "reports/tables/data/buyer_enrichment_summary.csv", "value")
    add_trace(trace, "Current analytical population", "APPEL_OFFRE_count", ao_count, "reports/tables/data/buyer_enrichment_summary.csv", "value")
    add_trace(trace, "Final selected proxy-event definition", "selected_method", selected_method, "reports/tables/linkage/final_selected_event_definition_current.csv", "selected_method")
    add_trace(trace, "Final selected proxy-event definition", "eligible_contracts", eligible, "reports/tables/linkage/final_selected_event_definition_current.csv", "eligible_contracts")
    add_trace(trace, "Final selected proxy-event definition", "proxy_recurrence_events", events, "reports/tables/linkage/final_selected_event_definition_current.csv", "event_count")
    add_trace(trace, "Final selected proxy-event definition", "event_rate", event_rate, "reports/tables/linkage/final_selected_event_definition_current.csv", "event_rate")
    add_trace(trace, "Survival results", "survival_24m", survival_24, "reports/tables/survival/survival_summary_current.csv", "survival_24m")
    add_trace(trace, "Survival results", "survival_60m", survival_60, "reports/tables/survival/survival_summary_current.csv", "survival_60m")
    add_trace(trace, "Operational indicators", "mean_p12", p12_mean, "reports/tables/survival/operational_risk_scores_current.csv", "p_renewal_12m")
    add_trace(trace, "Operational indicators", "mean_p24", p24_mean, "reports/tables/survival/operational_risk_scores_current.csv", "p_renewal_24m")
    add_trace(trace, "Operational indicators", "expected_renewals_12m", exp12, "reports/tables/survival/operational_risk_scores_current.csv", "p_renewal_12m")
    add_trace(trace, "Operational indicators", "expected_renewals_24m", exp24, "reports/tables/survival/operational_risk_scores_current.csv", "p_renewal_24m")
    add_trace(trace, "Methodology tests", "lightgbm_status", lightgbm_status, "reports/tables/validation/classifier_benchmark_current.csv", "status", "LightGBM requires the system OpenMP library libgomp.so.1 in this environment.")
    pd.DataFrame(trace).to_csv(ROOT / "reports" / "current_source_values_used.csv", index=False)

    methodology_text = "; ".join(methodology["conclusion"].astype(str).tolist())
    method_table = methods[["method", "variant", "event_count", "event_rate", "synthetic_benchmark_precision", "synthetic_benchmark_recall", "synthetic_benchmark_f1"]].copy()
    method_rows = "\n".join(
        f"{r.method} {r.variant} & {int(r.event_count)} & {100*r.event_rate:.1f}\\% & {r.synthetic_benchmark_precision:.3f} & {r.synthetic_benchmark_recall:.3f} & {r.synthetic_benchmark_f1:.3f} \\\\"
        for r in method_table.itertuples(index=False)
    )
    tex = rf"""
\documentclass[11pt]{{article}}
\usepackage[a4paper,margin=1in]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{graphicx}}
\usepackage{{hyperref}}
\usepackage{{float}}
\title{{Current BOAMP Proxy Recurrence Study}}
\author{{Gigalis internship project}}
\date{{Generated {utc_now()}}}
\begin{{document}}
\maketitle

\section{{Executive Summary}}
This report presents the current enriched BOAMP recurrence study for the Gigalis scope: Pays de la Loire digital BOAMP notices. The current dataset covers {actual_range}. It contains {retained_count:,} retained notices, including {ao_count:,} APPEL\_OFFRE notices. The selected current event definition is {selected_method}, producing {events:,} proxy recurrence events among {eligible:,} eligible contracts ({100*event_rate:.1f}\%). The event is a proxy recurrence, not a legally verified renewal.

\section{{Current Data Source and Study Period}}
Raw BOAMP records were downloaded from the BOAMP Opendatasoft API and cached under \texttt{{data/raw/boamp\_current}}. The requested scope keeps the existing internship population: Pays de la Loire departments and digital CPV divisions. The final retained notice count is {retained_count:,}, after deduplication from {raw_count:,} verified raw records. The censoring date used by the current analysis is {censoring}.

\section{{SIREN/SIRET Enrichment and Buyer-Key Construction}}
The current cleaning pipeline keeps raw buyer identifiers, cleaned SIRET, cleaned SIREN where available, SIREN derived from SIRET, and high-confidence external SIREN enrichment. It then constructs the buyer key in this order: valid SIRET, valid SIREN, SIREN extracted from SIRET, enriched SIREN, normalized buyer-name fallback. The current output has {valid_siret:,} rows with valid SIRET and {enriched_siren:,} rows with enriched SIREN.

\section{{Current Analytical Population}}
The survival unit remains APPEL\_OFFRE. ATTRIBUTION notices are used only to refine the start date when \texttt{{annonce\_lie}} links to an APPEL\_OFFRE and an award date is available. Contracts are eligible for linkage when their expected recurrence search window has opened before the current censoring date.

\begin{{figure}}[H]
\centering
\includegraphics[width=.82\linewidth]{{figures/data/analytical_population_funnel.pdf}}
\caption{{Current analytical population funnel. Source: \texttt{{reports/tables/data/analytical\_population\_summary.csv}}.}}
\end{{figure}}

\section{{Candidate-Pair Generation and Linkage Methods}}
Candidate pairs are generated within enriched buyer keys, restricted to later notices around the expected end date, and scored using text similarity, CPV compatibility, temporal proximity, buyer-key quality, generic CPV flags, rank, and score margin.

\begin{{table}}[H]
\centering
\begin{{tabular}}{{lrrrrr}}
\toprule
Method & Events & Event rate & Benchmark precision & Benchmark recall & F1 \\
\midrule
{method_rows}
\bottomrule
\end{{tabular}}
\caption{{Current method comparison. Benchmark metrics are synthetic/silver diagnostics, not real BOAMP ground truth.}}
\end{{table}}

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{figures/linkage/method_event_counts.pdf}}
\caption{{Current proxy recurrence event counts by method.}}
\end{{figure}}

\section{{Methodology Tests From Record-Linkage Literature}}
The current methodology diagnostics cover classifier benchmarks, blocking alternatives, text similarity alternatives, threshold zones, active-learning label budgets, subgroup audits, unique-link diagnostics, and weak external-reference diagnostics. Main conclusion: {methodology_text}

LightGBM is recorded in the classifier benchmark table as blocked by the missing system OpenMP library \texttt{{libgomp.so.1}}; it was not treated as evidence for the selected method. Other current classifier diagnostics, including logistic regression, random forest, gradient boosting, SVM, XGBoost, recordlinkage, and Splink diagnostics, were regenerated.

\section{{Final Selected Proxy-Event Definition}}
The selected current definition is {selected_method}. It is selected from current outputs using benchmark diagnostics, negative-control behavior, event sufficiency, generic-CPV risk, survival stability, interpretability, and implementation reliability. Real BOAMP precision and recall are not directly observed.

\section{{Current Survival Results}}
Under the selected current definition, Kaplan-Meier survival is {100*survival_24:.1f}\% at 24 months and {100*survival_60:.1f}\% at 60 months.

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{figures/survival/km_curve_current.pdf}}
\caption{{Kaplan-Meier curve under the selected current proxy-event definition.}}
\end{{figure}}

\section{{Current 12/24-Month Operational Indicators}}
The selected AFT model produces mean 12-month proxy recurrence probability {p12_mean:.3f} and mean 24-month probability {p24_mean:.3f}. Summed over scored contracts, expected recurrences are {exp12:.1f} within 12 months and {exp24:.1f} within 24 months.

\begin{{figure}}[H]
\centering
\includegraphics[width=.78\linewidth]{{figures/survival/p12_distribution_current.pdf}}
\caption{{Distribution of current 12-month operational recurrence probabilities.}}
\end{{figure}}

\section{{Limitations}}
BOAMP does not provide verified renewal-chain labels. All events are proxy recurrences: identifiable reappearances of similar procurement needs under the selected rule. Synthetic and weak external-reference diagnostics help compare methods but do not establish legal renewal truth. Buyer enrichment depends on public SIREN/SIRET availability and high-confidence matching only. The LightGBM classifier benchmark remains blocked by the missing system library \texttt{{libgomp.so.1}} and is explicitly excluded from method-selection evidence.

\section{{Next Steps}}
Prioritize manual review of possible-match-zone links, name-fallback buyer keys, generic CPV cases, low-margin links, and high-impact buyer or segment rankings. Incorporate reviewed labels into a future active-learning loop.

\end{{document}}
"""
    report_path = ROOT / "reports" / "current_boamp_recurrence_study_report.tex"
    report_path.write_text(tex, encoding="utf-8")
    append_run_log(
        [
            "",
            f"## Current report/source trace - {utc_now()}",
            f"- Report: {report_path}",
            "- Source trace: reports/current_source_values_used.csv",
        ]
    )
    print(f"Saved {report_path}")
    print("Saved reports/current_source_values_used.csv")


if __name__ == "__main__":
    main()
