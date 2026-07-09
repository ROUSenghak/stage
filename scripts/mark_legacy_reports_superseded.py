from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import ROOT, append_run_log, utc_now


CURRENT_REPORT = "reports/current_boamp_recurrence_study_report.pdf"
CURRENT_TEX = "reports/current_boamp_recurrence_study_report.tex"
CURRENT_TRACE = "reports/current_source_values_used.csv"
CURRENT_AUDIT = "reports/tables/audit/final_current_pipeline_audit.csv"


MARKDOWN_FILES = [
    ROOT / "reports" / "calibrated_event_definition_summary.md",
    ROOT / "reports" / "phase1_data_quality_report.md",
    ROOT / "reports" / "report_consistency_audit.md",
    ROOT / "reports" / "method_comparison_report_consistency_audit_20260708.md",
    ROOT / "reports" / "audit" / "report_consistency_findings.md",
    ROOT / "reports" / "audit" / "statistical_explanation_improvements.md",
    ROOT / "reports" / "week1_summary.md",
    ROOT / "reports" / "final_draft" / "README.md",
    ROOT / "boamp_renewal_linking_quality" / "README.md",
    ROOT / "validation_robustness" / "validation_robustness_report.md",
]

TEX_FILES = [
    ROOT / "reports" / "datasets_documentation.tex",
    ROOT / "reports" / "phase1_technical_report.tex",
    ROOT / "reports" / "internship_report.tex",
    ROOT / "reports" / "data_quality_report" / "data_quality_report.tex",
    ROOT / "reports" / "final_draft" / "gigalis_boamp_proxy_recurrence_survival_report.tex",
]

CSV_FILES = [
    ROOT / "reports" / "audit" / "current_results_audit.csv",
    ROOT / "reports" / "final_draft" / "source_values_used.csv",
]


def first_value(df: pd.DataFrame, metric: str) -> str:
    value = df.loc[df["metric"].eq(metric), "value"]
    if value.empty:
        return ""
    return str(value.iloc[0])


def current_summary() -> dict[str, str]:
    trace = pd.read_csv(ROOT / CURRENT_TRACE)
    return {
        "study_period": first_value(trace, "actual_date_range"),
        "raw_notice_count": first_value(trace, "raw_notice_count"),
        "retained_notice_count": first_value(trace, "retained_notice_count"),
        "appel_offre": first_value(trace, "APPEL_OFFRE_count"),
        "valid_siret_rows": first_value(trace, "valid_siret_rows"),
        "enriched_siren_rows": first_value(trace, "enriched_siren_rows"),
        "selected_method": first_value(trace, "selected_method"),
        "eligible_contracts": first_value(trace, "eligible_contracts"),
        "proxy_events": first_value(trace, "proxy_recurrence_events"),
        "event_rate": f"{float(first_value(trace, 'event_rate')):.1%}",
        "survival_24m": f"{float(first_value(trace, 'survival_24m')):.1%}",
        "survival_60m": f"{float(first_value(trace, 'survival_60m')):.1%}",
        "mean_p12": f"{float(first_value(trace, 'mean_p12')):.1%}",
        "mean_p24": f"{float(first_value(trace, 'mean_p24')):.1%}",
    }


def markdown_wrapper(path: Path, summary: dict[str, str]) -> str:
    rel = path.relative_to(ROOT)
    return f"""# Superseded Historical Artifact

This file used to describe an earlier BOAMP study snapshot. It is no longer an active source for the project narrative.

The active study is the **current enriched BOAMP recurrence study**. Use:

- Current report: `{CURRENT_REPORT}`
- Current LaTeX source: `{CURRENT_TEX}`
- Current source trace: `{CURRENT_TRACE}`
- Current final audit: `{CURRENT_AUDIT}`

## Current Study Snapshot

- Study period: {summary['study_period']}
- Raw / retained BOAMP notices: {summary['raw_notice_count']} / {summary['retained_notice_count']}
- APPEL_OFFRE notices: {summary['appel_offre']}
- Valid SIRET rows / enriched SIREN rows: {summary['valid_siret_rows']} / {summary['enriched_siren_rows']}
- Selected proxy-event method: {summary['selected_method']}
- Eligible contracts: {summary['eligible_contracts']}
- Proxy recurrence events: {summary['proxy_events']}
- Event rate: {summary['event_rate']}
- Survival at 24 / 60 months: {summary['survival_24m']} / {summary['survival_60m']}
- Mean operational p12 / p24: {summary['mean_p12']} / {summary['mean_p24']}

## Historical Status

The previous contents of `{rel}` are preserved in Git history and remote backups. They should not be cited as current results. In this project, recurrence events are proxy links derived from BOAMP records, not legally verified renewals.
"""


def tex_wrapper(path: Path, summary: dict[str, str]) -> str:
    title = path.stem.replace("_", " ").title()
    def esc(value: str) -> str:
        return (
            str(value)
            .replace("\\", r"\textbackslash{}")
            .replace("&", r"\&")
            .replace("%", r"\%")
            .replace("_", r"\_")
            .replace("#", r"\#")
        )

    return rf"""\documentclass[11pt]{{article}}
\usepackage[margin=2.5cm]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{hyperref}}
\title{{{esc(title)}: Superseded Historical Artifact}}
\date{{Current replacement generated {utc_now()}}}
\begin{{document}}
\maketitle

This document used to describe an earlier BOAMP study snapshot. It is no longer an active source for the project narrative. The active study is \textbf{{the current enriched BOAMP recurrence study}}.

\begin{{itemize}}
\item Current report: \texttt{{reports/current\_boamp\_recurrence\_study\_report.pdf}}
\item Current source trace: \texttt{{reports/current\_source\_values\_used.csv}}
\item Current final audit: \texttt{{reports/tables/audit/final\_current\_pipeline\_audit.csv}}
\end{{itemize}}

\section*{{Current Study Snapshot}}

\begin{{tabular}}{{ll}}
\toprule
Metric & Current value \\
\midrule
Study period & {esc(summary['study_period'])} \\
Raw / retained BOAMP notices & {esc(summary['raw_notice_count'])} / {esc(summary['retained_notice_count'])} \\
APPEL\_OFFRE notices & {esc(summary['appel_offre'])} \\
Valid SIRET / enriched SIREN rows & {esc(summary['valid_siret_rows'])} / {esc(summary['enriched_siren_rows'])} \\
Selected proxy-event method & {esc(summary['selected_method'])} \\
Eligible contracts & {esc(summary['eligible_contracts'])} \\
Proxy recurrence events & {esc(summary['proxy_events'])} \\
Event rate & {esc(summary['event_rate'])} \\
Survival at 24 / 60 months & {esc(summary['survival_24m'])} / {esc(summary['survival_60m'])} \\
Mean operational p12 / p24 & {esc(summary['mean_p12'])} / {esc(summary['mean_p24'])} \\
\bottomrule
\end{{tabular}}

\section*{{Historical Status}}

The previous contents of this file are preserved in Git history and remote backups. They should not be cited as current results. In this project, recurrence events are proxy links derived from BOAMP records, not legally verified renewals.

\end{{document}}
"""


def write_csv_wrapper(path: Path, summary: dict[str, str]) -> None:
    rows = [
        {"file": str(path.relative_to(ROOT)), "status": "superseded_historical_artifact", "current_source": CURRENT_REPORT, "note": "Previous contents preserved in Git history."},
        {"file": str(path.relative_to(ROOT)), "status": "current_snapshot", "current_source": CURRENT_TRACE, "note": f"Current study period {summary['study_period']}; selected method {summary['selected_method']}; proxy events {summary['proxy_events']}."},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    summary = current_summary()
    written = []
    for path in MARKDOWN_FILES:
        if path.exists():
            path.write_text(markdown_wrapper(path, summary), encoding="utf-8")
            written.append(str(path.relative_to(ROOT)))
    for path in TEX_FILES:
        if path.exists():
            path.write_text(tex_wrapper(path, summary), encoding="utf-8")
            written.append(str(path.relative_to(ROOT)))
    for path in CSV_FILES:
        if path.exists():
            write_csv_wrapper(path, summary)
            written.append(str(path.relative_to(ROOT)))
    append_run_log(
        [
            "",
            f"## Legacy report supersession - {utc_now()}",
            "- Rewrote active-facing historical report files as explicit superseded wrappers.",
            f"- Files updated: {len(written)}",
            *[f"  - {name}" for name in written],
        ]
    )
    print("Superseded historical report files:")
    for name in written:
        print(f"- {name}")


if __name__ == "__main__":
    main()
