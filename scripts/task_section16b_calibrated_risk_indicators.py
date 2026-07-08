"""
Section 16b — Operational Risk Indicators (12m / 24m) under the CALIBRATED
balanced event definition.

Same estimation design as scripts/task_section16_risk_indicators.py (LogNormal
AFT, same covariates, prediction date = study end 2024-12-31), but fitted on
data/processed/boamp_phase2_survival_calibrated_balanced.csv (the recommended
calibrated proxy-event rule) instead of the pre-calibration 665-event handoff.

Outputs (suffix `_calibrated_balanced`, originals untouched):

  reports/tables/survival/renewal_risk_12_24_months_calibrated_balanced.csv
  reports/tables/survival/top20_renewal_risk_calibrated_balanced.csv
  reports/tables/survival/buyer_renewal_risk_ranking_calibrated_balanced.csv
  reports/tables/survival/segment_renewal_risk_ranking_calibrated_balanced.csv
  reports/figures/survival/pred_hist_p12m_calibrated_balanced.png
  reports/figures/survival/pred_top20_contracts_calibrated_balanced.png

Optional CLI override for another survival dataset (e.g. the selected M2
balanced method from the 2026-07-08 method comparison):

  python scripts/task_section16b_calibrated_risk_indicators.py \
      data/processed/boamp_phase2_survival_method_m2_balanced.csv \
      _m2_balanced "M2 balanced (selected method)"
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from lifelines import LogNormalAFTFitter

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "boamp_phase2_survival_calibrated_balanced.csv"
FIG_DIR = ROOT / "reports" / "figures" / "survival"
TBL_DIR = ROOT / "reports" / "tables" / "survival"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TBL_DIR.mkdir(parents=True, exist_ok=True)

SUFFIX = "_calibrated_balanced"
RULE_LABEL = "calibrated balanced rule"
if len(sys.argv) >= 3:
    DATA_PATH = ROOT / sys.argv[1]
    SUFFIX = sys.argv[2]
    RULE_LABEL = sys.argv[3] if len(sys.argv) > 3 else SUFFIX.strip("_")
STUDY_END = pd.Timestamp("2024-12-31")
HIGH_THRESH = 0.40
MEDIUM_THRESH = 0.25

try:
    plt.style.use("seaborn-v0_8-paper")
except OSError:
    pass
plt.rcParams.update({
    "font.family": "serif", "font.size": 11,
    "axes.titlesize": 13, "axes.labelsize": 12,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "--",
    "lines.linewidth": 1.8, "figure.dpi": 120,
    "savefig.dpi": 300, "savefig.bbox": "tight",
    "legend.frameon": True, "legend.framealpha": 0.85,
})
PALETTE = ["#1b6ca8", "#e05c00", "#2a9d1e", "#9c27b0", "#c9b400"]


def save_fig(name: str):
    path = FIG_DIR / name
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close("all")
    print(f"  saved → {path}")


print(f"Loading survival data ({RULE_LABEL}) …")
df = pd.read_csv(DATA_PATH, parse_dates=["start_date"])
df["start_year"] = df["start_date"].dt.year
df["dur_was_imputed"] = (
    df["dur_was_imputed"].astype(str).str.lower().isin(["true", "1", "yes"]).astype(int)
)
rule_desc = str(df["event_definition"].iloc[0]) if "event_definition" in df.columns else "calibrated_balanced"

TOP_CATS = ["IT Services & Consulting", "Software & Applications",
            "Telecom & Networks", "Cybersecurity"]
df["cat_cox"] = df["category_label"].where(df["category_label"].isin(TOP_CATS), other="Other")
df["proc_cox"] = df["type_procedure"].replace({
    "RESTREINT": "Other_proc", "DIALOGUE_COMPETITIF": "Other_proc", "AUTRE": "Other_proc"
})

df_cox = df[["observed_duration_months", "event", "declared_duration_months",
             "dur_was_imputed", "start_year", "cat_cox", "proc_cox"]].dropna()
df_cox_enc = pd.get_dummies(df_cox, columns=["cat_cox", "proc_cox"],
                            drop_first=True, dtype=int)
print(f"  AFT dataset: {len(df_cox_enc):,} rows, {int(df_cox_enc['event'].sum())} events")

print("Fitting LogNormal AFT …")
lnaf = LogNormalAFTFitter(penalizer=0.1)
lnaf.fit(df_cox_enc, duration_col="observed_duration_months",
         event_col="event", show_progress=False)
print(f"  AIC={lnaf.AIC_:.1f}  C={lnaf.concordance_index_:.4f}")

print("\n[16b.1] Contract-level predictions …")
feature_df = df_cox_enc.drop(columns=["observed_duration_months", "event"])
sf12 = lnaf.predict_survival_function(feature_df, times=[12]).T.rename(columns={12: "S_12mo"})
sf24 = lnaf.predict_survival_function(feature_df, times=[24]).T.rename(columns={24: "S_24mo"})

risk_df = sf12.join(sf24)
risk_df.index = df_cox_enc.index
risk_df["p_renewal_12m"] = (1 - risk_df["S_12mo"]).round(4)
risk_df["p_renewal_24m"] = (1 - risk_df["S_24mo"]).round(4)


def _tier(p):
    if p >= HIGH_THRESH:
        return "High"
    if p >= MEDIUM_THRESH:
        return "Medium"
    return "Low"


risk_df["risk_tier"] = risk_df["p_renewal_12m"].apply(_tier)

meta_cols = ["contract_id", "renewal_contract_id", "buyer_key", "category_label",
             "start_date", "declared_duration_months", "dur_was_imputed",
             "event", "observed_duration_months"]
risk_df = risk_df.join(df[meta_cols])
risk_df["start_date"] = pd.to_datetime(risk_df["start_date"])
risk_df["age_months"] = ((STUDY_END - risk_df["start_date"]).dt.days / 30.44).round(2)
risk_df["model_used"] = "LogNormal AFT"
risk_df["event_definition_note"] = (
    f"{RULE_LABEL} proxy recurrence event ({rule_desc}); "
    "identifiable BOAMP re-publication, not a legally verified renewal."
)

out_cols = ["contract_id", "renewal_contract_id", "buyer_key", "category_label",
            "start_date", "age_months", "declared_duration_months", "dur_was_imputed",
            "event", "observed_duration_months",
            "p_renewal_12m", "p_renewal_24m", "risk_tier", "model_used",
            "event_definition_note"]
risk_out = risk_df[out_cols].reset_index(drop=True)
risk_out.to_csv(TBL_DIR / f"renewal_risk_12_24_months{SUFFIX}.csv", index=False)
print(f"  {len(risk_out):,} rows saved")
print(f"  Risk tiers: {risk_df['risk_tier'].value_counts().to_dict()}")
print(f"  Mean p12m={risk_df['p_renewal_12m'].mean():.4f}  mean p24m={risk_df['p_renewal_24m'].mean():.4f}")
print(f"  Max p12m={risk_df['p_renewal_12m'].max():.4f}")
print(f"  Expected renewals 12m={risk_df['p_renewal_12m'].sum():.1f}  24m={risk_df['p_renewal_24m'].sum():.1f}")

print("\n[16b.2] Buyer-level aggregation …")
buyer_grp = (
    risk_df.groupby("buyer_key")
    .agg(
        n_contracts=("contract_id", "count"),
        expected_renewals_12m=("p_renewal_12m", "sum"),
        expected_renewals_24m=("p_renewal_24m", "sum"),
        max_p_renewal_12m=("p_renewal_12m", "max"),
        mean_p_renewal_12m=("p_renewal_12m", "mean"),
        high_risk_contracts_count=("risk_tier", lambda x: (x == "High").sum()),
    )
    .reset_index()
    .round(4)
    .sort_values(["expected_renewals_12m", "buyer_key"], ascending=[False, True])
    .reset_index(drop=True)
)
buyer_grp.to_csv(TBL_DIR / f"buyer_renewal_risk_ranking{SUFFIX}.csv", index=False)
print(f"  {len(buyer_grp)} buyers saved")
print(buyer_grp.head(5)[["buyer_key", "n_contracts", "expected_renewals_12m"]].to_string(index=False))

print("\n[16b.3] Segment-level aggregation …")
seg_grp = (
    risk_df.groupby("category_label")
    .agg(
        n_contracts=("contract_id", "count"),
        expected_renewals_12m=("p_renewal_12m", "sum"),
        expected_renewals_24m=("p_renewal_24m", "sum"),
        mean_p_renewal_12m=("p_renewal_12m", "mean"),
        mean_p_renewal_24m=("p_renewal_24m", "mean"),
        high_risk_contracts_count=("risk_tier", lambda x: (x == "High").sum()),
    )
    .reset_index()
    .round(4)
    .sort_values(["expected_renewals_12m", "category_label"], ascending=[False, True])
    .reset_index(drop=True)
)
seg_grp.to_csv(TBL_DIR / f"segment_renewal_risk_ranking{SUFFIX}.csv", index=False)
print(seg_grp[["category_label", "n_contracts", "expected_renewals_12m"]].to_string(index=False))

print("\n[16b.4] Figures …")
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(risk_df["p_renewal_12m"], bins=40, color=PALETTE[0], edgecolor="white")
ax.axvline(HIGH_THRESH, color="red", linestyle="--", linewidth=1.5,
           label=f"High-risk threshold ({HIGH_THRESH:.2f})")
ax.axvline(MEDIUM_THRESH, color="orange", linestyle="--", linewidth=1.2,
           label=f"Medium-risk threshold ({MEDIUM_THRESH:.2f})")
ax.set_xlabel("P(recurrence ≤ 12 months)")
ax.set_ylabel("Contracts")
ax.set_title(f"LogNormal AFT — 12-Month Recurrence Probability ({RULE_LABEL})\n"
             f"(N={len(risk_df):,} scored contracts, {int(risk_df['event'].sum())} events)")
ax.legend(fontsize=9)
save_fig(f"pred_hist_p12m{SUFFIX}.png")

top20 = (
    risk_df[["contract_id", "category_label", "declared_duration_months",
             "p_renewal_12m", "p_renewal_24m", "risk_tier", "event"]]
    .sort_values(["p_renewal_12m", "contract_id"], ascending=[False, True])
    .head(20)
    .reset_index(drop=True)
)
top20.to_csv(TBL_DIR / f"top20_renewal_risk{SUFFIX}.csv", index=False)

labels = [f"{row.contract_id}\n({row.category_label[:12]})" for row in top20.itertuples()]
colors = [PALETTE[0] if t == "High" else PALETTE[1] if t == "Medium" else PALETTE[2]
          for t in top20["risk_tier"]]
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(range(len(top20)), top20["p_renewal_12m"], color=colors)
ax.set_yticks(range(len(top20)))
ax.set_yticklabels(labels, fontsize=7)
ax.set_xlabel("P(recurrence ≤ 12 months)")
ax.set_title(f"Top-20 Contracts by 12-Month Recurrence Probability\n(LogNormal AFT, {RULE_LABEL})")
ax.invert_yaxis()
from matplotlib.patches import Patch
legend_elems = [Patch(color=PALETTE[0], label="High"),
                Patch(color=PALETTE[1], label="Medium"),
                Patch(color=PALETTE[2], label="Low")]
ax.legend(handles=legend_elems, title="Risk tier", fontsize=9)
save_fig(f"pred_top20_contracts{SUFFIX}.png")

print(f"\nDone. Section 16b outputs regenerated under {RULE_LABEL} "
      f"({int(df['event'].sum())} events).")
