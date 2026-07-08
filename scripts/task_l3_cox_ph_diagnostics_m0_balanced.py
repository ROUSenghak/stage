"""
L3 gap closure (2026-07-08): the official M0-balanced Cox specification
(declared_duration_months, dur_was_imputed, start_year; penalizer=0.05;
C-index 0.544, matching reports/method_comparison_report_consistency_audit_20260708.md)
had never had its proportional-hazards assumption tested. Notebook 02's
Schoenfeld test only covers the old 665-event pre-calibration model.

This script fits the identical official spec on
data/processed/boamp_phase2_survival_method_m0_balanced.csv, runs the
Schoenfeld residual test, and produces a log-log diagnostic plot, so the L3
"validated Cox model" deliverable is validated on the actual selected dataset.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-stage-1")
warnings.filterwarnings("ignore")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.statistics import proportional_hazard_test

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

# The same reduced official spec is now PH-checked for both the conservative
# baseline (M0 balanced) and the selected main method (M2 balanced, promoted
# by the 2026-07-08 method-comparison rerun).
SPECS = [
    (
        "M0_balanced",
        ROOT / "data" / "processed" / "boamp_phase2_survival_method_m0_balanced.csv",
        ROOT / "reports" / "tables" / "survival" / "m0_balanced_cox_ph_assumption_test.csv",
        ROOT / "reports" / "figures" / "survival" / "m0_balanced_coxph_loglog_dur_imputed.png",
    ),
    (
        "M2_balanced",
        ROOT / "data" / "processed" / "boamp_phase2_survival_method_m2_balanced.csv",
        ROOT / "reports" / "tables" / "survival" / "m2_balanced_cox_ph_assumption_test.csv",
        ROOT / "reports" / "figures" / "survival" / "m2_balanced_coxph_loglog_dur_imputed.png",
    ),
]

ACADEMIC_PALETTE = ["#1b4d89", "#b85c38"]

for RULE_NAME, DATA_PATH, TABLE_OUT, FIGURE_OUT in SPECS:
    df = pd.read_csv(DATA_PATH, parse_dates=["start_date"])
    df["event"] = pd.to_numeric(df["event"], errors="coerce").fillna(0).astype(int)

    cox_df = df[["observed_duration_months", "event", "declared_duration_months", "dur_was_imputed", "start_date"]].copy()
    cox_df["declared_duration_months"] = pd.to_numeric(cox_df["declared_duration_months"], errors="coerce")
    cox_df["dur_was_imputed"] = pd.to_numeric(cox_df["dur_was_imputed"], errors="coerce").fillna(0)
    cox_df["start_year"] = pd.to_datetime(cox_df["start_date"], errors="coerce").dt.year
    cox_df = cox_df.drop(columns=["start_date"]).dropna()
    cox_df = cox_df.rename(columns={"observed_duration_months": "duration"})

    cph = CoxPHFitter(penalizer=0.05)
    cph.fit(cox_df, duration_col="duration", event_col="event")
    print(f"\n=== {RULE_NAME} ===")
    print(f"Official {RULE_NAME} Cox C-index: {cph.concordance_index_:.6f}")
    print(f"n = {len(cox_df)}, events = {int(cox_df['event'].sum())}")

    ph_test = proportional_hazard_test(cph, cox_df, time_transform="rank")
    ph_summary = ph_test.summary.reset_index().rename(columns={"index": "variable"})
    ph_summary["rule_name"] = RULE_NAME
    ph_summary["cox_c_index"] = cph.concordance_index_
    ph_summary["n_rows"] = len(cox_df)
    ph_summary["n_events"] = int(cox_df["event"].sum())
    ph_summary.to_csv(TABLE_OUT, index=False)
    print("\nSchoenfeld residual test (rank transform):")
    print(ph_summary[["variable", "test_statistic", "p"]].to_string(index=False))

    fig, ax = plt.subplots(figsize=(6.5, 4.3))
    for val, label, color in [(0, "Declared duration", ACADEMIC_PALETTE[0]), (1, "Imputed duration", ACADEMIC_PALETTE[1])]:
        sub = df[pd.to_numeric(df["dur_was_imputed"], errors="coerce").fillna(0).astype(int) == val]
        kmf = KaplanMeierFitter()
        kmf.fit(sub["observed_duration_months"], sub["event"])
        sf = kmf.survival_function_
        sf = sf[sf["KM_estimate"] > 0]
        loglog = np.log(-np.log(sf["KM_estimate"]))
        ax.plot(np.log(sf.index), loglog, label=label, color=color, drawstyle="steps-post", linewidth=1.4)
    ax.set_xlabel("log(time)")
    ax.set_ylabel("log(-log(S(t)))")
    ax.set_title(f"Log-log PH check — dur_was_imputed\n({RULE_NAME.replace('_', ' ')}, official Cox spec)")
    ax.legend()
    ax.grid(True, color="#d9d9d9", linewidth=0.45, alpha=0.7)
    fig.tight_layout()
    fig.savefig(FIGURE_OUT, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"\nWrote {TABLE_OUT.relative_to(ROOT)}")
    print(f"Wrote {FIGURE_OUT.relative_to(ROOT)}")

    violated = ph_summary[ph_summary["p"] < 0.05]["variable"].tolist()
    print(f"Covariates violating PH (p<0.05): {violated if violated else 'none'}")
