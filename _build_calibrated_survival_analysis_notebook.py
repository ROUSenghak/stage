from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / "notebooks" / "07_calibrated_survival_analysis.ipynb"


def md(source: str):
    return nbf.v4.new_markdown_cell(source.strip() + "\n")


def code(source: str):
    return nbf.v4.new_code_cell(source.strip() + "\n")


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "pygments_lexer": "ipython3"},
}

cells = []

cells.append(md(
    """
# Calibrated BOAMP Survival Analysis

This notebook runs the core survival diagnostics for the current event definitions:

- **M2 balanced** (`m2_balanced`) — the **selected main method** from the 2026-07-08 method-comparison rerun (probabilistic/active-learning-assisted linkage, threshold 0.65, 254 proxy events).
- **M0 balanced** (`balanced`) — the calibrated composite rule, kept as the **conservative transparent baseline** sensitivity.
- **M0 broad / M0 strict** — upper- and high-precision sensitivity bounds.

Real BOAMP event labels remain proxy recurrences: identifiable reappearances of similar procurement needs under the selected matching rule, not certified recurrence chains. The mapped manual audit is a plausibility diagnostic only (its sample was stratified on the pre-calibration baseline's links), and only the synthetic benchmark provides directly observable precision/recall.
"""
))

cells.append(code(
    r"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from lifelines import KaplanMeierFitter, CoxPHFitter, LogNormalAFTFitter, WeibullAFTFitter, LogLogisticAFTFitter

_cwd = Path.cwd()
PROJ = _cwd
for candidate in [_cwd, *_cwd.parents]:
    if (candidate / "data").exists() and (candidate / "notebooks").exists():
        PROJ = candidate
        break
os.chdir(PROJ)

PROCESSED = PROJ / "data" / "processed"
REPORT_TABLES = PROJ / "reports" / "tables" / "survival"
VALIDATION_TABLES = PROJ / "reports" / "tables" / "validation"
REPORT_FIGURES = PROJ / "reports" / "figures" / "survival"

REPORT_TABLES.mkdir(parents=True, exist_ok=True)
REPORT_FIGURES.mkdir(parents=True, exist_ok=True)

ACADEMIC_PALETTE = ["#1b4d89", "#b85c38", "#2f6f4e", "#7a5195", "#5c677d", "#8a6f3f"]
sns.set_theme(context="paper", style="ticks", palette=ACADEMIC_PALETTE, font="serif")
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif", "Times"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "legend.frameon": False,
    "figure.dpi": 140,
    "savefig.dpi": 300,
    "grid.color": "#d9d9d9",
    "grid.linewidth": 0.45,
    "grid.alpha": 0.7,
})
"""
))

cells.append(md("## 1. Load Calibrated Survival Datasets"))

cells.append(code(
    r"""
rule_paths = {
    "broad": PROCESSED / "boamp_phase2_survival_calibrated_broad.csv",
    "balanced": PROCESSED / "boamp_phase2_survival_calibrated_balanced.csv",
    "strict": PROCESSED / "boamp_phase2_survival_calibrated_strict.csv",
    # Selected main method (2026-07-08 method comparison): M2 balanced.
    "m2_balanced": PROCESSED / "boamp_phase2_survival_method_m2_balanced.csv",
}
missing = [name for name, path in rule_paths.items() if not path.exists()]
if missing:
    raise SystemExit("Missing calibrated survival datasets: " + ", ".join(missing))

dfs = {}
for name, path in rule_paths.items():
    d = pd.read_csv(path, parse_dates=["start_date"])
    d["rule_name"] = name
    d["start_year"] = d["start_date"].dt.year
    d["event"] = pd.to_numeric(d["event"], errors="coerce").fillna(0).astype(int)
    d["observed_duration_months"] = pd.to_numeric(d["observed_duration_months"], errors="coerce")
    d["declared_duration_months"] = pd.to_numeric(d["declared_duration_months"], errors="coerce")
    d["dur_was_imputed"] = d["dur_was_imputed"].astype(str).str.lower().isin(["true", "1", "yes"]).astype(int)
    dfs[name] = d

loaded = pd.DataFrame([
    {
        "rule_name": name,
        "path": str(path.relative_to(PROJ)),
        "rows": len(dfs[name]),
        "events": int(dfs[name]["event"].sum()),
        "event_rate": float(dfs[name]["event"].mean()),
    }
    for name, path in rule_paths.items()
])
display(loaded)
"""
))

cells.append(md("## 2. Kaplan-Meier Summary"))

cells.append(code(
    r"""
km_rows = []
kmf = KaplanMeierFitter()
time_points = [12, 24, 36, 48, 60]
for name, d in dfs.items():
    kmf.fit(d["observed_duration_months"], event_observed=d["event"], label=name)
    row = {
        "rule_name": name,
        "n": len(d),
        "events": int(d["event"].sum()),
        "event_rate": float(d["event"].mean()),
        "km_median_months": float(kmf.median_survival_time_) if np.isfinite(kmf.median_survival_time_) else np.inf,
    }
    for t in time_points:
        row[f"survival_{t}m"] = float(kmf.survival_function_at_times(t).iloc[0])
    km_rows.append(row)

km_summary = pd.DataFrame(km_rows)
km_summary.to_csv(REPORT_TABLES / "calibrated_rule_km_summary.csv", index=False)
display(km_summary)
"""
))

cells.append(code(
    r"""
def style_axes(ax, grid_axis="y"):
    ax.grid(True, axis=grid_axis, color="#d9d9d9", linewidth=0.45, alpha=0.7)
    ax.grid(False, axis="x" if grid_axis == "y" else "y")
    sns.despine(ax=ax, trim=True)
    return ax

def savefig(name):
    fig = plt.gcf()
    for ax in fig.axes:
        style_axes(ax)
    path = REPORT_FIGURES / name
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.show()
    print(path)

fig, ax = plt.subplots(figsize=(7.0, 4.6))
for name in ["broad", "balanced", "m2_balanced", "strict"]:
    d = dfs[name]
    kmf.fit(d["observed_duration_months"], event_observed=d["event"], label=f"{name} ({int(d['event'].sum())} events)")
    kmf.plot_survival_function(ax=ax, ci_show=False, linewidth=1.4)
ax.set_title("Kaplan-Meier curves under current proxy-event definitions")
ax.set_xlabel("Observed duration (months)")
ax.set_ylabel("Survival probability")
savefig("calibrated_rules_km_curves.png")
"""
))

cells.append(md("## 3. Cox Models Across Event Definitions"))

cells.append(code(
    r"""
def fit_cox_for_rule(name: str, d: pd.DataFrame):
    model_df = d[["observed_duration_months", "event", "declared_duration_months", "start_year", "dur_was_imputed", "category_label"]].copy()
    top_cats = model_df["category_label"].value_counts().head(5).index
    model_df["category_model"] = np.where(model_df["category_label"].isin(top_cats), model_df["category_label"], "Other")
    model_df = pd.get_dummies(model_df.drop(columns=["category_label"]), columns=["category_model"], drop_first=True)
    model_df = model_df.dropna()
    cph = CoxPHFitter(penalizer=0.1)
    cph.fit(model_df, duration_col="observed_duration_months", event_col="event")
    s = cph.summary.reset_index().rename(columns={"index": "variable"})
    if "variable" not in s.columns and "covariate" in s.columns:
        s = s.rename(columns={"covariate": "variable"})
    s["rule_name"] = name
    s["c_index"] = cph.concordance_index_
    s["n_events"] = int(model_df["event"].sum())
    s["n_rows"] = len(model_df)
    return s, cph

cox_tables = []
cox_models = {}
for name, d in dfs.items():
    try:
        table, model = fit_cox_for_rule(name, d)
        cox_tables.append(table)
        cox_models[name] = model
    except Exception as exc:
        cox_tables.append(pd.DataFrame([{"rule_name": name, "variable": "MODEL_FAILED", "error": str(exc)}]))

cox_comparison = pd.concat(cox_tables, ignore_index=True)
cox_comparison.to_csv(REPORT_TABLES / "calibrated_rule_cox_comparison.csv", index=False)
display_cols = [c for c in ["rule_name", "variable", "coef", "exp(coef)", "p", "c_index", "n_events"] if c in cox_comparison.columns]
display(cox_comparison[display_cols].head(40))
"""
))

cells.append(code(
    r"""
plot_vars = ["declared_duration_months", "start_year", "dur_was_imputed"]
coef_plot = cox_comparison[cox_comparison["variable"].isin(plot_vars)].copy()
if not coef_plot.empty:
    coef_plot["hr"] = coef_plot["exp(coef)"]
    coef_plot["hr_low"] = coef_plot["exp(coef) lower 95%"]
    coef_plot["hr_high"] = coef_plot["exp(coef) upper 95%"]
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    y_labels = []
    y_positions = []
    pos = 0
    for var in plot_vars:
        for rule in ["broad", "balanced", "m2_balanced", "strict"]:
            r = coef_plot[(coef_plot["variable"].eq(var)) & (coef_plot["rule_name"].eq(rule))]
            if len(r):
                rr = r.iloc[0]
                ax.errorbar(rr["hr"], pos, xerr=[[rr["hr"] - rr["hr_low"]], [rr["hr_high"] - rr["hr"]]], fmt="o", capsize=2, label=rule if pos < 4 else None)
                y_labels.append(f"{var} | {rule}")
                y_positions.append(pos)
                pos += 1
    ax.axvline(1.0, color="#222222", linestyle="--", linewidth=0.8)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels)
    ax.set_xlabel("Hazard ratio")
    ax.set_title("Cox hazard ratios under calibrated event definitions")
    ax.legend()
    savefig("calibrated_rules_cox_hazard_ratios.png")
"""
))

cells.append(md(
    """
## 3b. Cox PH Assumption Check (Official Reduced Spec, M0 and M2 Balanced)

Schoenfeld residual test on the reduced 3-covariate spec (`declared_duration_months`, `dur_was_imputed`, `start_year`; penalizer 0.05) used in the method-comparison rerun, for the selected main method (M2 balanced) and the conservative baseline (M0 balanced).
"""
))

cells.append(code(
    r"""
from lifelines.statistics import proportional_hazard_test

ph_specs = [
    ("M0_balanced", PROCESSED / "boamp_phase2_survival_method_m0_balanced.csv",
     REPORT_TABLES / "m0_balanced_cox_ph_assumption_test.csv"),
    ("M2_balanced", PROCESSED / "boamp_phase2_survival_method_m2_balanced.csv",
     REPORT_TABLES / "m2_balanced_cox_ph_assumption_test.csv"),
]
ph_results = {}
for rule_name, data_path, table_out in ph_specs:
    ph_df = pd.read_csv(data_path, parse_dates=["start_date"])
    ph_df["event"] = pd.to_numeric(ph_df["event"], errors="coerce").fillna(0).astype(int)
    spec = ph_df[["observed_duration_months", "event", "declared_duration_months", "dur_was_imputed", "start_date"]].copy()
    spec["declared_duration_months"] = pd.to_numeric(spec["declared_duration_months"], errors="coerce")
    spec["dur_was_imputed"] = pd.to_numeric(spec["dur_was_imputed"], errors="coerce").fillna(0)
    spec["start_year"] = pd.to_datetime(spec["start_date"], errors="coerce").dt.year
    spec = spec.drop(columns=["start_date"]).dropna().rename(columns={"observed_duration_months": "duration"})
    cph_official = CoxPHFitter(penalizer=0.05)
    cph_official.fit(spec, duration_col="duration", event_col="event")
    ph_test = proportional_hazard_test(cph_official, spec, time_transform="rank")
    ph_summary = ph_test.summary.reset_index().rename(columns={"index": "variable"})
    ph_summary["rule_name"] = rule_name
    ph_summary["cox_c_index"] = cph_official.concordance_index_
    ph_summary["n_rows"] = len(spec)
    ph_summary["n_events"] = int(spec["event"].sum())
    ph_summary.to_csv(table_out, index=False)
    ph_results[rule_name] = ph_summary
    print(f"{rule_name}: C-index {cph_official.concordance_index_:.4f}, events {int(spec['event'].sum())}")
    display(ph_summary[["variable", "test_statistic", "p", "cox_c_index"]])
    violated = ph_summary[ph_summary["p"] < 0.05]["variable"].tolist()
    print(f"Covariates violating PH (p<0.05): {violated if violated else 'none'}\n")
"""
))

cells.append(md("## 4. Parametric AFT Check (Selected M2 Balanced and M0 Balanced Baseline)"))

cells.append(code(
    r"""
def aft_comparison_for(d: pd.DataFrame):
    aft_df = d[["observed_duration_months", "event", "declared_duration_months", "start_year", "dur_was_imputed"]].dropna()
    rows = []
    for model_name, cls in [
        ("WeibullAFT", WeibullAFTFitter),
        ("LogNormalAFT", LogNormalAFTFitter),
        ("LogLogisticAFT", LogLogisticAFTFitter),
    ]:
        try:
            m = cls(penalizer=0.01)
            m.fit(aft_df, duration_col="observed_duration_months", event_col="event")
            rows.append({
                "model": model_name,
                "AIC": float(m.AIC_),
                "log_likelihood": float(m.log_likelihood_),
                "n_rows": len(aft_df),
                "n_events": int(aft_df["event"].sum()),
            })
        except Exception as exc:
            rows.append({"model": model_name, "AIC": np.nan, "log_likelihood": np.nan, "error": str(exc)})
    return pd.DataFrame(rows).sort_values("AIC")

aft_comparison = aft_comparison_for(dfs["balanced"])
aft_comparison.to_csv(REPORT_TABLES / "calibrated_balanced_aft_comparison.csv", index=False)
print("M0 balanced (conservative baseline):")
display(aft_comparison)

m2_aft_comparison = aft_comparison_for(dfs["m2_balanced"])
m2_aft_comparison.to_csv(REPORT_TABLES / "m2_balanced_aft_comparison.csv", index=False)
print("M2 balanced (selected main method):")
display(m2_aft_comparison)

# AIC values are comparable across models fitted on the SAME dataset, not
# across event definitions: M0 and M2 define different event sets, so their
# likelihoods are not on a common scale.
"""
))

cells.append(md("## 5. Verification and Conclusion"))

cells.append(code(
    r"""
expected = [
    REPORT_TABLES / "calibrated_rule_km_summary.csv",
    REPORT_TABLES / "calibrated_rule_cox_comparison.csv",
    REPORT_TABLES / "calibrated_balanced_aft_comparison.csv",
    REPORT_TABLES / "m2_balanced_aft_comparison.csv",
    REPORT_TABLES / "m0_balanced_cox_ph_assumption_test.csv",
    REPORT_TABLES / "m2_balanced_cox_ph_assumption_test.csv",
    REPORT_FIGURES / "calibrated_rules_km_curves.png",
    REPORT_FIGURES / "calibrated_rules_cox_hazard_ratios.png",
]
verification = pd.DataFrame([
    {"file": str(p.relative_to(PROJ)), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else 0}
    for p in expected
])
verification["status"] = np.where(verification["exists"] & (verification["size_bytes"] > 0), "PASS", "FAIL")
verification.to_csv(REPORT_TABLES / "calibrated_survival_analysis_verification.csv", index=False)
display(verification)
if (verification["status"] != "PASS").any():
    raise SystemExit("Verification failed.")

m2_summary = km_summary[km_summary["rule_name"].eq("m2_balanced")].iloc[0]
m0_summary = km_summary[km_summary["rule_name"].eq("balanced")].iloc[0]
print("FINAL STATUS: PASS")
print(f"Selected main (M2 balanced) events: {int(m2_summary['events'])} / {int(m2_summary['n'])} ({m2_summary['event_rate']:.1%})")
print(f"Conservative baseline (M0 balanced) events: {int(m0_summary['events'])} / {int(m0_summary['n'])} ({m0_summary['event_rate']:.1%})")
print(f"M2 balanced KM median: {m2_summary['km_median_months']}")
print("Report M0 balanced, broad, and strict as sensitivity specifications.")
"""
))

cells.append(md(
    """
## Final Interpretation

The **selected main method is M2 balanced** (254 proxy events / 1,210 eligible, 21.0%), promoted by the 2026-07-08 method-comparison rerun: with the synthetic benchmark scored by the same Sentence-Transformer encoder as the real pipeline, M2 balanced improves benchmark-estimated precision (0.612 vs 0.575) and recall (0.733 vs 0.568) over M0 balanced, has a lower real-data negative-control acceptance rate (7.9% vs 9.4%), a smaller synthetic-to-real accepted-link profile shift, and enough events for stable Cox/AFT estimation. **M0 balanced** (269 events, 22.2%) is retained as the conservative, fully transparent rule-based baseline; broad and strict are sensitivity bounds. Headline survival results are stable across M0 and M2 balanced (12-month survival 95.9% vs 95.6%; 24-month 92.3% vs 92.1%), so the substantive conclusions do not hinge on the method choice.

The mapped manual-audit precision is a plausibility diagnostic only: the audit sample was stratified on the pre-calibration baseline's own links, so it cannot fairly arbitrate between M0, M1, and M2.

The survival conclusions should be reported as conditional on the proxy-event construction. Real BOAMP does not supply certified recurrence-chain labels; benchmark precision/recall are estimated on a controlled BOAMP-like synthetic dataset, not on real BOAMP.
"""
))

nb["cells"] = cells
NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, NOTEBOOK)
print(f"Wrote {NOTEBOOK}")
