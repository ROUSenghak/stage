"""
Section 16 — Operational Risk Indicators (12m / 24m)

Standalone script that re-fits the LogNormal AFT model on the current
boamp_phase2_survival.csv (665 events, W=6 temporal window) and regenerates:

  reports/tables/survival/renewal_risk_12_24_months.csv
  reports/tables/survival/buyer_renewal_risk_ranking.csv
  reports/tables/survival/segment_renewal_risk_ranking.csv
  reports/figures/survival/pred_hist_p12m.png
  reports/figures/survival/pred_hist_p24m.png
  reports/figures/survival/pred_top20_contracts.png
  reports/figures/survival/pred_top15_buyers.png
  reports/figures/survival/pred_segment_expected.png
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from lifelines import LogNormalAFTFitter, CoxPHFitter

# ── paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "boamp_phase2_survival.csv"
FIG_DIR   = ROOT / "reports" / "figures" / "survival"
TBL_DIR   = ROOT / "reports" / "tables"  / "survival"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TBL_DIR.mkdir(parents=True, exist_ok=True)

STUDY_END = pd.Timestamp("2024-12-31")
HIGH_THRESH   = 0.40
MEDIUM_THRESH = 0.25

# ── figure style (matches notebook) ────────────────────────────────────────
try:
    plt.style.use("seaborn-v0_8-paper")
except OSError:
    try:
        plt.style.use("seaborn-paper")
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


# ── load & prepare data (mirrors notebook sections 3-10) ───────────────────
print("Loading data …")
df = pd.read_csv(DATA_PATH, parse_dates=["start_date"])
df["start_year"]      = df["start_date"].dt.year
df["dur_was_imputed"] = df["dur_was_imputed"].astype(int)

TOP_CATS = ["IT Services & Consulting", "Software & Applications",
            "Telecom & Networks", "Cybersecurity"]
df["cat_cox"]  = df["category_label"].where(df["category_label"].isin(TOP_CATS), other="Other")
df["proc_cox"] = df["type_procedure"].replace({
    "RESTREINT": "Other_proc", "DIALOGUE_COMPETITIF": "Other_proc", "AUTRE": "Other_proc"
})

df_cox = df[["observed_duration_months", "event", "declared_duration_months",
             "dur_was_imputed", "start_year", "cat_cox", "proc_cox"]].dropna()
df_cox_enc = pd.get_dummies(df_cox, columns=["cat_cox", "proc_cox"],
                             drop_first=True, dtype=int)
print(f"  Cox dataset: {len(df_cox_enc):,} rows, {int(df_cox_enc['event'].sum())} events")

# ── fit LogNormal AFT ───────────────────────────────────────────────────────
print("Fitting LogNormal AFT …")
lnaf = LogNormalAFTFitter(penalizer=0.1)
lnaf.fit(df_cox_enc, duration_col="observed_duration_months",
         event_col="event", show_progress=False)
print(f"  AIC={lnaf.AIC_:.1f}  C={lnaf.concordance_index_:.4f}")

# ── 16.1 Contract-level predictions ────────────────────────────────────────
print("\n[16.1] Contract-level predictions …")
feature_df = df_cox_enc.drop(columns=["observed_duration_months", "event"])

sf12 = lnaf.predict_survival_function(feature_df, times=[12]).T.rename(columns={12: "S_12mo"})
sf24 = lnaf.predict_survival_function(feature_df, times=[24]).T.rename(columns={24: "S_24mo"})

risk_df = sf12.join(sf24)
risk_df.index = df_cox_enc.index
risk_df["p_renewal_12m"] = (1 - risk_df["S_12mo"]).round(4)
risk_df["p_renewal_24m"] = (1 - risk_df["S_24mo"]).round(4)

def _tier(p):
    if p >= HIGH_THRESH:   return "High"
    if p >= MEDIUM_THRESH: return "Medium"
    return "Low"

risk_df["risk_tier"] = risk_df["p_renewal_12m"].apply(_tier)

meta_cols = ["contract_id", "renewal_contract_id", "buyer_key", "category_label",
             "start_date", "declared_duration_months", "dur_was_imputed",
             "event", "observed_duration_months"]
risk_df = risk_df.join(df[meta_cols])
risk_df["start_date"] = pd.to_datetime(risk_df["start_date"])
risk_df["age_months"] = ((STUDY_END - risk_df["start_date"]).dt.days / 30.44).round(2)
risk_df["model_used"]  = "LogNormal AFT"
risk_df["event_definition_note"] = (
    "Proxy BOAMP renewal event from algorithmic linking; not manually validated yet."
)

out_cols = ["contract_id", "renewal_contract_id", "buyer_key", "category_label",
            "start_date", "age_months", "declared_duration_months", "dur_was_imputed",
            "event", "observed_duration_months",
            "p_renewal_12m", "p_renewal_24m", "risk_tier", "model_used",
            "event_definition_note"]
risk_out = risk_df[out_cols].reset_index(drop=True)
risk_out.to_csv(TBL_DIR / "renewal_risk_12_24_months.csv", index=False)
print(f"  {len(risk_out):,} rows saved")
tier_counts = risk_df["risk_tier"].value_counts()
print(f"  Risk tiers: {tier_counts.to_dict()}")

# ── 16.2 Buyer-level aggregation ───────────────────────────────────────────
print("\n[16.2] Buyer-level aggregation …")
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
    .sort_values("expected_renewals_12m", ascending=False)
    .reset_index(drop=True)
)
buyer_grp.to_csv(TBL_DIR / "buyer_renewal_risk_ranking.csv", index=False)
print(f"  {len(buyer_grp)} buyers saved")
print(f"  Top 5:\n{buyer_grp.head(5)[['buyer_key','n_contracts','expected_renewals_12m']].to_string(index=False)}")

# ── 16.3 Segment-level aggregation ─────────────────────────────────────────
print("\n[16.3] Segment-level aggregation …")
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
    .sort_values("expected_renewals_12m", ascending=False)
    .reset_index(drop=True)
)
seg_grp.to_csv(TBL_DIR / "segment_renewal_risk_ranking.csv", index=False)
print(f"  {len(seg_grp)} segments saved")
print(seg_grp[["category_label", "n_contracts", "expected_renewals_12m"]].to_string(index=False))

# ── 16.4 Prediction histogram — 12m ────────────────────────────────────────
print("\n[16.4] Figures …")
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(risk_df["p_renewal_12m"], bins=40, color=PALETTE[0], edgecolor="white")
ax.axvline(HIGH_THRESH,   color="red",    linestyle="--", linewidth=1.5,
           label=f"High-risk threshold ({HIGH_THRESH:.2f})")
ax.axvline(MEDIUM_THRESH, color="orange", linestyle="--", linewidth=1.2,
           label=f"Medium-risk threshold ({MEDIUM_THRESH:.2f})")
ax.set_xlabel("P(renewal ≤ 12 months)")
ax.set_ylabel("Contracts")
ax.set_title(f"LogNormal AFT — 12-Month Renewal Probability Distribution\n"
             f"(N={len(risk_df):,} scored contracts, {int(risk_df['event'].sum())} events)")
ax.legend(fontsize=9)
save_fig("pred_hist_p12m.png")

# ── 16.5 Prediction histogram — 24m ────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(risk_df["p_renewal_24m"], bins=40, color=PALETTE[1], edgecolor="white")
ax.set_xlabel("P(renewal ≤ 24 months)")
ax.set_ylabel("Contracts")
ax.set_title(f"LogNormal AFT — 24-Month Renewal Probability Distribution\n"
             f"(N={len(risk_df):,} scored contracts, {int(risk_df['event'].sum())} events)")
save_fig("pred_hist_p24m.png")

# ── 16.6 Top-20 contracts by 12m risk ──────────────────────────────────────
top20 = (
    risk_df[["contract_id", "category_label", "declared_duration_months",
             "p_renewal_12m", "p_renewal_24m", "risk_tier", "event"]]
    .sort_values("p_renewal_12m", ascending=False)
    .head(20)
    .reset_index(drop=True)
)
top20.to_csv(TBL_DIR / "top20_renewal_risk.csv", index=False)

labels = [f"{row.contract_id}\n({row.category_label[:12]})"
          for row in top20.itertuples()]
colors = [PALETTE[0] if t == "High" else PALETTE[1] if t == "Medium" else PALETTE[2]
          for t in top20["risk_tier"]]

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(range(len(top20)), top20["p_renewal_12m"], color=colors)
ax.set_yticks(range(len(top20)))
ax.set_yticklabels(labels, fontsize=7)
ax.set_xlabel("P(renewal ≤ 12 months)")
ax.set_title("Top-20 Contracts by 12-Month Renewal Probability\n(LogNormal AFT)")
ax.invert_yaxis()
from matplotlib.patches import Patch
legend_elems = [Patch(color=PALETTE[0], label="High"),
                Patch(color=PALETTE[1], label="Medium"),
                Patch(color=PALETTE[2], label="Low")]
ax.legend(handles=legend_elems, title="Risk tier", fontsize=9)
save_fig("pred_top20_contracts.png")

# ── 16.7 Top-15 buyers by expected renewals (12m) ──────────────────────────
top15_buyers = buyer_grp.head(15)
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(range(len(top15_buyers)), top15_buyers["expected_renewals_12m"],
        color=PALETTE[0], alpha=0.85)
ax.barh(range(len(top15_buyers)), top15_buyers["expected_renewals_24m"],
        color=PALETTE[1], alpha=0.45, label="24m additional")
short_keys = [k[:40] + "…" if len(k) > 40 else k
              for k in top15_buyers["buyer_key"]]
ax.set_yticks(range(len(top15_buyers)))
ax.set_yticklabels(short_keys, fontsize=8)
ax.invert_yaxis()
ax.set_xlabel("Expected renewals (Σ predicted probability)")
ax.set_title("Top-15 Buyers by Expected Renewals (12-Month Horizon)\n(LogNormal AFT)")
ax.legend(["12m", "24m"], fontsize=9)
save_fig("pred_top15_buyers.png")

# ── 16.8 Segment expected renewals ─────────────────────────────────────────
x = range(len(seg_grp))
width = 0.38
short_cats = [c[:18] + "…" if len(c) > 18 else c for c in seg_grp["category_label"]]
fig, ax = plt.subplots(figsize=(11, 5))
ax.bar([i - width / 2 for i in x], seg_grp["expected_renewals_12m"],
       width, color=PALETTE[0], label="12 months")
ax.bar([i + width / 2 for i in x], seg_grp["expected_renewals_24m"],
       width, color=PALETTE[1], label="24 months")
ax.set_xticks(list(x))
ax.set_xticklabels(short_cats, rotation=35, ha="right", fontsize=9)
ax.set_ylabel("Expected renewals (Σ predicted probability)")
ax.set_title("Expected Renewals by Technology Segment\n(LogNormal AFT — 12m and 24m horizons)")
ax.legend(fontsize=9)
save_fig("pred_segment_expected.png")

print("\nDone. All Section 16 outputs regenerated with 665-event model (W=6).")
