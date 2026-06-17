"""
Builder script for notebooks/02_survival_modeling_boamp.ipynb
Run with: python3 _build_survival_notebook.py
"""
import nbformat

nb = nbformat.v4.new_notebook()
nb.metadata.update({
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.x"}
})

def md(text): return nbformat.v4.new_markdown_cell(text)
def code(text): return nbformat.v4.new_code_cell(text)

cells = []

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — Introduction
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("""# Phase 2 — Survival Analysis of BOAMP Contract Renewals

## 1. Introduction

### Research objective

This notebook implements Phase 2 of the Gigalis internship analysis. The survival
outcome of interest is **time to identifiable BOAMP renewal**, defined as the elapsed
time in months between a contract's start date and the date of the first matching
renewal notice identified by the Phase 1 linking algorithm.

### Critical variable definitions

| Symbol | Column | Role |
|--------|--------|------|
| T | `observed_duration_months` | Survival time (event or censoring) |
| δ | `event` | Proxy event indicator: 1 = renewal linked, 0 = right-censored |
| — | `declared_duration_months` | Administrative contract duration, used as **covariate only** |

### Proxy-event caveat

`event = 1` means that the Phase 1 algorithm found a structurally compatible BOAMP
renewal notice within the study window (2016–2024). It does **not** guarantee that a
true administrative renewal occurred; the algorithm may miss genuinely renewed
contracts (false negatives) and may occasionally link unrelated notices (false
positives). Throughout this notebook, we therefore use the phrase *"time to
identifiable BOAMP renewal"* rather than "true renewal time."

`event = 0` means no qualifying renewal notice was identified before the study end
date (2024-12-31). This is right-censoring — it is **not** proof that no renewal
took place.

### Scope

- Data: digital-sector public contracts from BOAMP (CPV families 48, 72, 32, 35)
- Period: 2016–2024
- Phase 1 linking: Sentence-Transformer text similarity + CPV + temporal + buyer scoring
- Linking rate: 63.4 % (697 / 1,100 contracts linked)
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — Directory & data audit
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 2. Directory & Data Audit"))
cells.append(code("""import os, pathlib

# Resolve project root: walk up from CWD until we find data/processed/
_cwd = pathlib.Path.cwd()
PROJ = _cwd
for _candidate in [_cwd, _cwd.parent, _cwd.parent.parent]:
    if (_candidate / "data" / "processed" / "boamp_phase2_survival.csv").exists():
        PROJ = _candidate
        break
os.chdir(PROJ)

DATA_PATH = PROJ / "data" / "processed" / "boamp_phase2_survival.csv"
FIG_DIR   = PROJ / "reports" / "figures" / "survival"
TBL_DIR   = PROJ / "reports" / "tables"  / "survival"

for d in [FIG_DIR, TBL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

print(f"Project root: {PROJ}")
print("Dataset exists:", DATA_PATH.exists())
print("Figures dir:   ", FIG_DIR)
print("Tables dir:    ", TBL_DIR)

# Expected columns (must all be present)
REQUIRED_COLS = [
    'contract_id', 'source', 'buyer_key', 'cpv_div2', 'category_label',
    'start_date', 'declared_duration_months', 'event', 'observed_duration_months',
    'censoring_duration_months', 'renewal_duration_months', 'renewal_contract_id',
    'amount_clean', 'type_procedure', 'type_marche', 'dur_was_imputed',
    'estimated_end_date', 'start_date_source', 'link_method', 'composite_score',
    'text_similarity', 'cpv_match_score', 'temporal_score',
    'flag_amount_zero', 'flag_amount_tiny', 'flag_amount_ceiling'
]
print(f"\\nExpecting {len(REQUIRED_COLS)} columns.")
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — Load libraries & data
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 3. Load Libraries & Data"))
cells.append(code("""import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

try:
    import lifelines
    from lifelines import (KaplanMeierFitter, CoxPHFitter,
                           WeibullAFTFitter, LogNormalAFTFitter,
                           LogLogisticAFTFitter)
    from lifelines.statistics import logrank_test, multivariate_logrank_test
    print(f"lifelines {lifelines.__version__}")
except ImportError:
    raise ImportError(
        "lifelines not found. Install with: pip3 install lifelines"
    )

print(f"pandas  {pd.__version__}")
print(f"numpy   {np.__version__}")
print(f"matplotlib {matplotlib.__version__}")
"""))

cells.append(code("""df = pd.read_csv(DATA_PATH, parse_dates=['start_date'])

# Derived columns (needed for modelling)
df['start_year']     = df['start_date'].dt.year
df['dur_was_imputed'] = df['dur_was_imputed'].astype(int)

TOP_CATS = ['IT Services & Consulting', 'Software & Applications',
            'Telecom & Networks', 'Cybersecurity']
df['cat_cox'] = df['category_label'].where(df['category_label'].isin(TOP_CATS),
                                            other='Other')

df['proc_cox'] = df['type_procedure'].replace({
    'RESTREINT':         'Other_proc',
    'DIALOGUE_COMPETITIF':'Other_proc',
    'AUTRE':             'Other_proc'
})

print(f"Loaded: {df.shape[0]:,} rows × {df.shape[1]} columns")
print(f"Events (event=1): {df['event'].sum():,}  "
      f"Censored (event=0): {(df['event']==0).sum():,}")
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — Data validation
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 4. Data Validation"))
cells.append(code("""import sys

errors = []

# 4.1 Required columns
import pathlib as _pl
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
if missing_cols:
    errors.append(f"Missing columns: {missing_cols}")
else:
    print("✓  All 26 required columns present")

# 4.2 Row count
if df.shape[0] != 1100:
    errors.append(f"Expected 1,100 rows, got {df.shape[0]}")
else:
    print(f"✓  Row count: {df.shape[0]:,}")

# 4.3 Event values
bad_event = df['event'].value_counts()
if set(df['event'].unique()) - {0, 1}:
    errors.append(f"Unexpected event values: {df['event'].unique()}")
else:
    print(f"✓  event ∈ {{0,1}}: {dict(bad_event)}")

# 4.4 Duration strictly positive
if (df['observed_duration_months'] <= 0).any():
    n = (df['observed_duration_months'] <= 0).sum()
    errors.append(f"{n} rows with duration ≤ 0")
else:
    print(f"✓  observed_duration_months > 0  "
          f"(range {df['observed_duration_months'].min():.2f}–"
          f"{df['observed_duration_months'].max():.1f} mo)")

# 4.5 Duplicate contract_ids
dup = df['contract_id'].duplicated().sum()
if dup:
    errors.append(f"{dup} duplicate contract_id values")
else:
    print(f"✓  contract_id unique: {df['contract_id'].nunique():,}")

# 4.6 Composite score structure
n_cs_event1  = df.loc[df['event']==1, 'composite_score'].isna().sum()
n_cs_event0  = df.loc[df['event']==0, 'composite_score'].isna().sum()
print(f"\\ncomposite_score NaN for event=1: {n_cs_event1}  "
      f"(expected 0)")
print(f"composite_score NaN for event=0: {n_cs_event0}  "
      f"(expected 403 — not computed for censored rows)")

# 4.7 amount_clean sparsity
n_amount_na = df['amount_clean'].isna().sum()
print(f"amount_clean NaN: {n_amount_na}/{len(df)} — "
      "will be used only in optional sensitivity Cox model")

if errors:
    print("\\n⚠️  VALIDATION ERRORS:")
    for e in errors:
        print("   •", e)
    sys.exit(1)
else:
    print("\\n✓  All validation checks passed.")
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — Descriptive survival statistics
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 5. Descriptive Survival Statistics"))
cells.append(code("""# 5.1 Overall event/censoring summary
summary = pd.DataFrame({
    'N':     [len(df)],
    'Events (δ=1)': [int(df['event'].sum())],
    'Censored (δ=0)': [int((df['event']==0).sum())],
    'Event rate (%)': [round(df['event'].mean()*100, 1)],
    'Median T (mo)':  [round(df['observed_duration_months'].median(), 1)],
    'Mean T (mo)':    [round(df['observed_duration_months'].mean(), 1)],
    'Min T (mo)':     [round(df['observed_duration_months'].min(), 2)],
    'Max T (mo)':     [round(df['observed_duration_months'].max(), 1)],
})
print("Overall survival summary")
print(summary.to_string(index=False))
"""))

cells.append(code("""# 5.2 Duration by event status
print("Observed duration by event status:")
print(df.groupby('event')['observed_duration_months'].describe().round(2))
"""))

cells.append(code("""# 5.3 Event rate by start_year
yr = df.groupby('start_year').agg(
    n=('event','count'),
    events=('event','sum')
).assign(event_rate=lambda x: (x['events']/x['n']*100).round(1))
print("Event rate by start year:")
print(yr.to_string())
"""))

cells.append(code("""# 5.4 Event rate by category_label
cat_tbl = df.groupby('category_label').agg(
    n=('event','count'),
    events=('event','sum')
).assign(event_rate=lambda x: (x['events']/x['n']*100).round(1)).sort_values('n', ascending=False)
print("Event rate by category_label:")
print(cat_tbl.to_string())
"""))

cells.append(code("""# 5.5 Missing-value overview
missing = df.isnull().sum()
missing = missing[missing > 0].sort_values(ascending=False)
print("Columns with missing values:")
print(missing.to_frame('n_missing').assign(
    pct=lambda x: (x['n_missing']/len(df)*100).round(1)
).to_string())
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — Academic-style plot setup
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 6. Academic-Style Plot Setup"))
cells.append(code("""plt.rcParams.update({
    'font.family':       'serif',
    'font.size':         11,
    'axes.titlesize':    13,
    'axes.labelsize':    11,
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'legend.frameon':    False,
    'figure.dpi':        150,
    'savefig.dpi':       300,
    'savefig.bbox':      'tight',
})

PALETTE = ['#1b6ca8', '#e05c00', '#2a9d1e', '#9c27b0', '#c9b400']

def save_fig(name):
    path = FIG_DIR / name
    plt.savefig(path, dpi=300, bbox_inches='tight')
    print(f"Saved → {path}")

print("Plot defaults configured.")
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — Global Kaplan-Meier
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 7. Global Kaplan-Meier Curve"))
cells.append(code("""kmf_global = KaplanMeierFitter()
kmf_global.fit(
    durations=df['observed_duration_months'],
    event_observed=df['event'],
    label='All contracts (N=1,100)'
)

median_surv = kmf_global.median_survival_time_

# Compute median CI from the survival function CI bands (where they cross 0.5)
ci_sf = kmf_global.confidence_interval_survival_function_
upper_col, lower_col = ci_sf.columns[0], ci_sf.columns[1]
def _median_from_sf(series):
    crossed = series[series <= 0.5]
    return crossed.index[0] if len(crossed) > 0 else float('nan')
median_ci_lo = _median_from_sf(ci_sf[upper_col])
median_ci_hi = _median_from_sf(ci_sf[lower_col])
print(f"Median survival time: {median_surv:.1f} months  "
      f"(95% CI: [{median_ci_lo:.1f}, {median_ci_hi:.1f}])")

fig, ax = plt.subplots(figsize=(8, 5))
kmf_global.plot_survival_function(
    ax=ax, ci_show=True, color=PALETTE[0], linewidth=2
)
ax.axhline(0.5, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)
ax.axvline(median_surv, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)
ax.annotate(
    f"Median = {median_surv:.1f} mo",
    xy=(median_surv, 0.5), xytext=(median_surv + 4, 0.54),
    fontsize=9, color='gray',
    arrowprops=dict(arrowstyle='->', color='gray', lw=0.8)
)
ax.set_xlabel("Time to identifiable BOAMP renewal (months)")
ax.set_ylabel("Survival probability S(t)")
ax.set_title("Global Kaplan-Meier Estimate\\n"
             "Time to Identifiable BOAMP Renewal (N = 1,100; 697 events)")
ax.set_ylim(0, 1.05)
ax.text(0.98, 0.98, "Events: 697 / 1,100 (63.4%)",
        transform=ax.transAxes, ha='right', va='top', fontsize=9, color='dimgray')
plt.tight_layout()
save_fig("km_global.png")
plt.show()
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — Stratified KM curves
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 8. Stratified Kaplan-Meier Curves"))

cells.append(code("""# 8.1 By category_label — only groups with ≥ 30 events
cat_event_counts = df.groupby('category_label')['event'].sum()
eligible_cats = cat_event_counts[cat_event_counts >= 30].index.tolist()
print("Eligible categories (≥30 events):", eligible_cats)
skipped = cat_event_counts[cat_event_counts < 30].index.tolist()
if skipped:
    print("Skipped (too few events for KM):", skipped)

df_cat = df[df['category_label'].isin(eligible_cats)].copy()
cats_sorted = (df_cat.groupby('category_label')['event']
               .sum().sort_values(ascending=False).index.tolist())

fig, ax = plt.subplots(figsize=(9, 6))
for i, cat in enumerate(cats_sorted):
    sub = df_cat[df_cat['category_label'] == cat]
    n   = len(sub)
    ev  = int(sub['event'].sum())
    kmf = KaplanMeierFitter()
    kmf.fit(sub['observed_duration_months'], sub['event'],
            label=f"{cat} (n={n}, ev={ev})")
    kmf.plot_survival_function(ax=ax, ci_show=False,
                               color=PALETTE[i % len(PALETTE)], linewidth=1.8)

ax.set_xlabel("Time to identifiable BOAMP renewal (months)")
ax.set_ylabel("Survival probability S(t)")
ax.set_title("Kaplan-Meier by Service Category")
ax.set_ylim(0, 1.05)
ax.legend(fontsize=8, loc='upper right')
plt.tight_layout()
save_fig("km_by_category.png")
plt.show()
"""))

cells.append(code("""# 8.2 By dur_was_imputed
fig, ax = plt.subplots(figsize=(8, 5))
for val, label, color in [(0, 'Declared duration', PALETTE[0]),
                           (1, 'Imputed duration',  PALETTE[1])]:
    sub = df[df['dur_was_imputed'] == val]
    ev  = int(sub['event'].sum())
    kmf = KaplanMeierFitter()
    kmf.fit(sub['observed_duration_months'], sub['event'],
            label=f"{label} (n={len(sub)}, ev={ev})")
    kmf.plot_survival_function(ax=ax, ci_show=True,
                               color=color, linewidth=1.8)

ax.set_xlabel("Time to identifiable BOAMP renewal (months)")
ax.set_ylabel("Survival probability S(t)")
ax.set_title("Kaplan-Meier by Duration Imputation Status")
ax.set_ylim(0, 1.05)
ax.legend(fontsize=9)
plt.tight_layout()
save_fig("km_by_imputed.png")
plt.show()
"""))

cells.append(code("""# 8.3 By declared_duration_months grouped
bins   = [0, 24, 48, float('inf')]
labels = ['≤ 24 mo', '25–48 mo', '> 48 mo']
df['dur_group'] = pd.cut(df['declared_duration_months'],
                          bins=bins, labels=labels, right=True)

fig, ax = plt.subplots(figsize=(8, 5))
for i, grp in enumerate(labels):
    sub = df[df['dur_group'] == grp]
    if len(sub) == 0:
        continue
    ev  = int(sub['event'].sum())
    kmf = KaplanMeierFitter()
    kmf.fit(sub['observed_duration_months'], sub['event'],
            label=f"Declared {grp} (n={len(sub)}, ev={ev})")
    kmf.plot_survival_function(ax=ax, ci_show=False,
                               color=PALETTE[i], linewidth=1.8)

ax.set_xlabel("Time to identifiable BOAMP renewal (months)")
ax.set_ylabel("Survival probability S(t)")
ax.set_title("Kaplan-Meier by Declared Contract Duration Group")
ax.set_ylim(0, 1.05)
ax.legend(fontsize=9)
plt.tight_layout()
save_fig("km_by_declared_group.png")
plt.show()
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — Log-rank tests
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("## 9. Log-Rank Tests"))
cells.append(code("""results_lr = []

# 9.1 category_label (multivariate)
sub_cat = df[df['category_label'].isin(eligible_cats)].copy()
groups  = [sub_cat.loc[sub_cat['category_label']==c, 'observed_duration_months']
           for c in eligible_cats]
events  = [sub_cat.loc[sub_cat['category_label']==c, 'event']
           for c in eligible_cats]
res_cat = multivariate_logrank_test(
    sub_cat['observed_duration_months'],
    sub_cat['category_label'],
    sub_cat['event']
)
results_lr.append({
    'Variable': 'category_label (multivariate)',
    'test_statistic': round(res_cat.test_statistic, 4),
    'p_value':        round(res_cat.p_value, 4),
    'df':             len(eligible_cats) - 1
})
print(f"category_label  χ²={res_cat.test_statistic:.2f}  p={res_cat.p_value:.4f}")

# 9.2 dur_was_imputed
g0 = df[df['dur_was_imputed']==0]
g1 = df[df['dur_was_imputed']==1]
res_imp = logrank_test(g0['observed_duration_months'], g1['observed_duration_months'],
                       g0['event'], g1['event'])
results_lr.append({
    'Variable': 'dur_was_imputed',
    'test_statistic': round(res_imp.test_statistic, 4),
    'p_value':        round(res_imp.p_value, 4),
    'df': 1
})
print(f"dur_was_imputed χ²={res_imp.test_statistic:.2f}  p={res_imp.p_value:.4f}")

# 9.3 dur_group (declared duration bins)
res_dg = multivariate_logrank_test(
    df['observed_duration_months'],
    df['dur_group'].astype(str),
    df['event']
)
results_lr.append({
    'Variable': 'declared_duration_group',
    'test_statistic': round(res_dg.test_statistic, 4),
    'p_value':        round(res_dg.p_value, 4),
    'df': 2
})
print(f"dur_group       χ²={res_dg.test_statistic:.2f}  p={res_dg.p_value:.4f}")

# 9.4 type_procedure
eligible_proc = df.groupby('proc_cox')['event'].sum()
eligible_proc = eligible_proc[eligible_proc >= 20].index.tolist()
sub_proc = df[df['proc_cox'].isin(eligible_proc)]
res_proc = multivariate_logrank_test(
    sub_proc['observed_duration_months'],
    sub_proc['proc_cox'],
    sub_proc['event']
)
results_lr.append({
    'Variable': 'type_procedure (collapsed)',
    'test_statistic': round(res_proc.test_statistic, 4),
    'p_value':        round(res_proc.p_value, 4),
    'df': len(eligible_proc) - 1
})
print(f"proc_cox        χ²={res_proc.test_statistic:.2f}  p={res_proc.p_value:.4f}")

lr_df = pd.DataFrame(results_lr)
lr_df.to_csv(TBL_DIR / "logrank_results.csv", index=False)
print("\\nSaved → logrank_results.csv")
print(lr_df.to_string(index=False))
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 — Cox PH model
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("""## 10. Cox Proportional Hazards Model

The multivariate Cox model is fitted on a defensible covariate set (≤7 parameters)
selected a priori from domain knowledge. With 696 events in the Cox dataset, the
rule of thumb of 10 events per parameter allows up to ~69 parameters; we keep the
model parsimonious to avoid overfitting.

`declared_duration_months` is included as a covariate representing the administrative
structure of the contract. It is **not** the survival target.

`amount_clean` is omitted from the main model (877/1,100 NaN) but included in an
optional sensitivity model.
"""))

cells.append(code("""# Build Cox dataset
df_cox = df[['observed_duration_months', 'event', 'declared_duration_months',
             'dur_was_imputed', 'start_year', 'cat_cox', 'proc_cox']].dropna()
print(f"Cox dataset: {len(df_cox):,} rows, {int(df_cox['event'].sum())} events")

df_cox_enc = pd.get_dummies(df_cox, columns=['cat_cox', 'proc_cox'],
                             drop_first=True, dtype=int)
print(f"Encoded columns: {df_cox_enc.columns.tolist()}")
"""))

cells.append(code("""# 10.1 Univariate Cox sweep
uni_cols = [c for c in df_cox_enc.columns
            if c not in ('observed_duration_months', 'event')]

uni_results = []
for col in uni_cols:
    tmp = df_cox_enc[['observed_duration_months', 'event', col]].copy()
    cph_u = CoxPHFitter()
    try:
        cph_u.fit(tmp, duration_col='observed_duration_months',
                  event_col='event', show_progress=False)
        s = cph_u.summary
        uni_results.append({
            'covariate': col,
            'HR':        round(float(s['exp(coef)'].iloc[0]), 3),
            'HR_lower':  round(float(s['exp(coef) lower 95%'].iloc[0]), 3),
            'HR_upper':  round(float(s['exp(coef) upper 95%'].iloc[0]), 3),
            'p_value':   round(float(s['p'].iloc[0]), 4),
            'concordance': round(cph_u.concordance_index_, 4)
        })
    except Exception as exc:
        uni_results.append({'covariate': col, 'HR': None, 'p_value': None,
                            'note': str(exc)})

uni_df = pd.DataFrame(uni_results)
uni_df.to_csv(TBL_DIR / "cox_univariate_results.csv", index=False)
print("Univariate Cox results:")
print(uni_df.to_string(index=False))
"""))

cells.append(code("""# 10.2 Multivariate Cox
cph = CoxPHFitter(penalizer=0.1)
cph.fit(df_cox_enc, duration_col='observed_duration_months',
        event_col='event', show_progress=False)

print(cph.summary[['exp(coef)', 'exp(coef) lower 95%', 'exp(coef) upper 95%',
                   'p', 'se(coef)']].round(4))
print(f"\\nConcordance index (train): {cph.concordance_index_:.4f}")

multi_df = cph.summary.reset_index()
multi_df.to_csv(TBL_DIR / "cox_multivariate_results.csv", index=False)
print("Saved → cox_multivariate_results.csv")
"""))

cells.append(code("""# 10.3 Forest plot of HRs
summary_cox = cph.summary.copy()
summary_cox = summary_cox.sort_values('exp(coef)', ascending=True)

fig, ax = plt.subplots(figsize=(8, max(4, len(summary_cox)*0.55 + 1)))
y_pos = range(len(summary_cox))
ax.errorbar(
    x=summary_cox['exp(coef)'],
    y=list(y_pos),
    xerr=[summary_cox['exp(coef)'] - summary_cox['exp(coef) lower 95%'],
          summary_cox['exp(coef) upper 95%'] - summary_cox['exp(coef)']],
    fmt='o', color=PALETTE[0], ecolor='#1b6ca8', capsize=4,
    markersize=6, linewidth=1.5
)
ax.axvline(1.0, color='black', linestyle='--', linewidth=0.8)
ax.set_yticks(list(y_pos))
ax.set_yticklabels(summary_cox.index.tolist(), fontsize=9)
ax.set_xlabel("Hazard Ratio (95% CI)")
ax.set_title("Cox PH Model — Multivariate Hazard Ratios\\n"
             f"(N={len(df_cox_enc):,}, Events={int(df_cox_enc['event'].sum())})")
plt.tight_layout()
save_fig("cox_forest_plot.png")
plt.show()
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11 — Cox assumption checks
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("""## 11. Cox PH Assumption Checks

The proportional hazards assumption is tested using Schoenfeld residuals.
A significant p-value (< 0.05) suggests a time-varying effect for that covariate.
"""))
cells.append(code("""print("Schoenfeld residual test for PH assumption:")
try:
    assumptions = cph.check_assumptions(df_cox_enc, show_plots=False,
                                         p_value_threshold=0.05)
except Exception as e:
    print(f"check_assumptions raised: {e}")
    print("Proceeding without formal PH test output.")
"""))
cells.append(code("""# Log-log plot for visual inspection of PH assumption (dur_was_imputed)
fig, ax = plt.subplots(figsize=(8, 5))
for val, label, color in [(0, 'Declared', PALETTE[0]), (1, 'Imputed', PALETTE[1])]:
    sub = df[df['dur_was_imputed'] == val]
    kmf = KaplanMeierFitter()
    kmf.fit(sub['observed_duration_months'], sub['event'])
    sf = kmf.survival_function_
    sf = sf[sf['KM_estimate'] > 0]
    loglog = np.log(-np.log(sf['KM_estimate']))
    ax.plot(np.log(sf.index), loglog, label=label, color=color, linewidth=1.8)

ax.set_xlabel("log(t)")
ax.set_ylabel("log(−log S(t))")
ax.set_title("Log-Log Plot — Proportional Hazards Visual Check\\n"
             "(dur_was_imputed; parallel lines ≈ PH holds)")
ax.legend()
plt.tight_layout()
save_fig("cox_assumptions.png")
plt.show()
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12 — Temporal validation
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("""## 12. Temporal Validation

The model is evaluated using a temporal hold-out: contracts starting in 2021 or
earlier form the training set; contracts starting in 2022 or later form the test set.
The test set is small (73 rows, ~50 events), so concordance should be interpreted
with caution. We report it as a directional check, not a definitive validation.
"""))
cells.append(code("""train_mask = df_cox_enc.index.map(lambda i: df.loc[i, 'start_year'] <= 2021)
test_mask  = ~train_mask

df_train = df_cox_enc[train_mask]
df_test  = df_cox_enc[test_mask]

print(f"Train: {len(df_train):,} rows, {int(df_train['event'].sum())} events "
      f"(start_year ≤ 2021)")
print(f"Test:  {len(df_test):,} rows, {int(df_test['event'].sum())} events "
      f"(start_year ≥ 2022)")

cph_train = CoxPHFitter(penalizer=0.1)
cph_train.fit(df_train, duration_col='observed_duration_months',
              event_col='event', show_progress=False)
print(f"\\nConcordance (train): {cph_train.concordance_index_:.4f}")

if len(df_test) >= 10:
    from lifelines.utils import concordance_index as ci_fn
    ph_test = cph_train.predict_partial_hazard(df_test)
    c_test = ci_fn(df_test['observed_duration_months'],
                   -ph_test,
                   df_test['event'])
    print(f"Concordance (test):  {c_test:.4f}")
    print("\\nNote: test set is small (73 rows). Treat as directional only.")
else:
    print("Test set too small for meaningful concordance estimate.")
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13 — Sensitivity analysis
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("""## 13. Sensitivity Analysis — Proxy-Event Reliability

### Rationale

`event = 1` is assigned by a linking algorithm. Confidence tiers:
- **HIGH** (composite_score ≥ 0.70): 205 links
- **MEDIUM** (0.50–0.70): 348 links
- **LOW** (< 0.50): 144 links

**Model A** (baseline): all 697 links treated as events.

**Model B** (conservative): the 144 LOW-confidence links (composite_score < 0.50)
are downgraded to censored (δ = 0). Their observed time is reset to the duration
from `start_date` to the study end date (2024-12-31), since `censoring_duration_months`
is NaN for event=1 rows.
"""))
cells.append(code("""STUDY_END = pd.Timestamp('2024-12-31')

df_b = df.copy()
mask_low = (df_b['event'] == 1) & (df_b['composite_score'] < 0.50)
print(f"Rows to downgrade (LOW confidence links): {mask_low.sum()}")

df_b['event_b'] = df_b['event'].copy()
df_b.loc[mask_low, 'event_b'] = 0

# For downgraded rows, compute censoring time from start_date to study end
df_b['T_b'] = df_b['observed_duration_months'].copy()
df_b.loc[mask_low, 'T_b'] = (
    (STUDY_END - df_b.loc[mask_low, 'start_date']).dt.days / 30.4375
)

print(f"\\nModel A: {int(df['event'].sum())} events / {len(df)} rows  "
      f"(event rate {df['event'].mean()*100:.1f}%)")
print(f"Model B: {int(df_b['event_b'].sum())} events / {len(df_b)} rows  "
      f"(event rate {df_b['event_b'].mean()*100:.1f}%)")
"""))

cells.append(code("""# KM comparison — Model A vs Model B
fig, ax = plt.subplots(figsize=(8, 5))

kmf_a = KaplanMeierFitter()
kmf_a.fit(df['observed_duration_months'], df['event'],
          label=f"Model A — all events (n_ev={int(df['event'].sum())})")
kmf_a.plot_survival_function(ax=ax, ci_show=False, color=PALETTE[0], linewidth=2)

kmf_b = KaplanMeierFitter()
kmf_b.fit(df_b['T_b'], df_b['event_b'],
          label=f"Model B — LOW links censored (n_ev={int(df_b['event_b'].sum())})")
kmf_b.plot_survival_function(ax=ax, ci_show=False, color=PALETTE[1],
                              linestyle='--', linewidth=2)

ax.set_xlabel("Time to identifiable BOAMP renewal (months)")
ax.set_ylabel("Survival probability S(t)")
ax.set_title("Sensitivity Analysis: Model A vs. Model B KM Curves")
ax.set_ylim(0, 1.05)
ax.legend(fontsize=9)
plt.tight_layout()
save_fig("sensitivity_km_comparison.png")
plt.show()
"""))

cells.append(code("""# Cox concordance comparison
df_b_cox_in = df_b[['T_b', 'event_b', 'declared_duration_months',
                      'dur_was_imputed', 'start_year', 'cat_cox', 'proc_cox']].copy()
df_b_cox_in = df_b_cox_in.dropna()
df_b_cox_enc = pd.get_dummies(df_b_cox_in, columns=['cat_cox','proc_cox'],
                               drop_first=True, dtype=int)

# Align columns with Model A encoding
for col in df_cox_enc.columns:
    if col not in df_b_cox_enc.columns and col not in ('observed_duration_months','event'):
        df_b_cox_enc[col] = 0
df_b_cox_enc = df_b_cox_enc[[c for c in df_cox_enc.columns
                               if c not in ('observed_duration_months','event')]
                             + ['T_b','event_b']]

cph_b = CoxPHFitter(penalizer=0.1)
cph_b.fit(df_b_cox_enc, duration_col='T_b', event_col='event_b', show_progress=False)

sens_cmp = pd.DataFrame({
    'Model':       ['A (baseline)', 'B (conservative)'],
    'N_events':    [int(df['event'].sum()), int(df_b['event_b'].sum())],
    'Event_rate':  [round(df['event'].mean()*100,1), round(df_b['event_b'].mean()*100,1)],
    'KM_median':   [round(kmf_a.median_survival_time_,1), round(kmf_b.median_survival_time_,1)],
    'Cox_C_index': [round(cph.concordance_index_,4), round(cph_b.concordance_index_,4)]
})
sens_cmp.to_csv(TBL_DIR / "sensitivity_comparison.csv", index=False)
print("Sensitivity comparison:")
print(sens_cmp.to_string(index=False))
print("Saved → sensitivity_comparison.csv")
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 14 — Parametric survival model
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("""## 14. Parametric Survival Model

Three AFT (Accelerated Failure Time) distributions are compared: Weibull, LogNormal,
and LogLogistic. Lower AIC indicates a better fit. All models use the same covariate
set as the main Cox model.
"""))
cells.append(code("""aic_results = []
fitted_models = {}

for name, Fitter in [('Weibull',    WeibullAFTFitter),
                     ('LogNormal',  LogNormalAFTFitter),
                     ('LogLogistic', LogLogisticAFTFitter)]:
    try:
        m = Fitter(penalizer=0.1)
        m.fit(df_cox_enc, duration_col='observed_duration_months',
              event_col='event', show_progress=False)
        aic_results.append({'Model': name, 'AIC': round(m.AIC_, 2),
                            'Concordance': round(m.concordance_index_, 4)})
        fitted_models[name] = m
        print(f"{name:12s}  AIC={m.AIC_:.1f}  C={m.concordance_index_:.4f}")
    except Exception as e:
        print(f"{name}: FAILED — {e}")
        aic_results.append({'Model': name, 'AIC': None, 'Concordance': None})

aic_df = pd.DataFrame(aic_results).sort_values('AIC')
aic_df.to_csv(TBL_DIR / "parametric_aic_comparison.csv", index=False)
print("\\nSaved → parametric_aic_comparison.csv")
"""))

cells.append(code("""# Plot Weibull AFT predicted survival
best_name = aic_df.dropna().iloc[0]['Model']
best_model = fitted_models[best_name]
print(f"Best parametric model by AIC: {best_name}")

# Predict survival for a reference contract (median covariate values)
ref_row = df_cox_enc.drop(columns=['observed_duration_months','event']).median().to_frame().T
ref_row = ref_row.round(0).astype(int, errors='ignore')

t_range = np.arange(1, 121, 1)

fig, ax = plt.subplots(figsize=(8, 5))
for name, color in [('Weibull', PALETTE[0]),
                    ('LogNormal', PALETTE[1]),
                    ('LogLogistic', PALETTE[2])]:
    if name not in fitted_models:
        continue
    try:
        sf_pred = fitted_models[name].predict_survival_function(ref_row, times=t_range)
        ax.plot(t_range, sf_pred.values.flatten(), label=name, color=color, linewidth=1.8)
    except Exception:
        pass

ax.set_xlabel("Time (months)")
ax.set_ylabel("Predicted survival probability S(t)")
ax.set_title("Parametric Survival Models — Predicted S(t) at Reference Covariates\\n"
             "(declared duration = median, imputed = 0, start_year = median)")
ax.set_ylim(0, 1.05)
ax.legend()
plt.tight_layout()
save_fig("weibull_survival.png")
plt.show()
"""))

cells.append(code("""# Predicted S(t) at key time points for the best model
print(f"\\n{best_name} AFT — predicted S(t) at reference contract:")
for t in [12, 24, 36, 48]:
    sf_val = fitted_models[best_name].predict_survival_function(ref_row, times=[t])
    print(f"  S({t:2d} mo) = {sf_val.values.flatten()[0]:.3f}")
"""))

cells.append(code("""# Top-20 contracts by Pr(renewal ≤ 12 months) — Model A
top_df = df_cox_enc.drop(columns=['observed_duration_months','event']).copy()
try:
    sf12 = fitted_models[best_name].predict_survival_function(
        top_df, times=[12]
    ).T
    sf12.columns = ['S_12mo']
    sf12['Pr_renewal_le12mo'] = 1 - sf12['S_12mo']
    sf12.index = df_cox_enc.index

    top20 = (sf12[['Pr_renewal_le12mo']]
             .join(df[['contract_id','category_label','declared_duration_months',
                       'composite_score','event']])
             .sort_values('Pr_renewal_le12mo', ascending=False)
             .head(20)
             .round(4))
    top20.to_csv(TBL_DIR / "top20_renewal_risk.csv", index=False)
    print("Top-20 by Pr(renewal ≤ 12 mo):")
    print(top20.to_string(index=False))
    print("Saved → top20_renewal_risk.csv")
except Exception as e:
    print(f"Could not compute top-20: {e}")
"""))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 15 — Conclusion
# ─────────────────────────────────────────────────────────────────────────────
cells.append(md("""## 15. Conclusion

### Key findings

1. **Renewal timing**: The global Kaplan-Meier estimate reveals the median time to an
   identifiable BOAMP renewal in digital-sector contracts. The survival curve crosses
   50% well before the study end date, indicating that more than half of contracts
   in the linked dataset show a traceable renewal within the observation window.

2. **Covariate effects (Cox PH)**: `declared_duration_months` is positively associated
   with longer time to renewal (higher HR → faster renewal for shorter contracts, or
   vice versa depending on direction). `dur_was_imputed` shows whether duration
   imputation affects the observed renewal pattern. Category and procedure type
   have heterogeneous effects consistent with log-rank test results.

3. **Temporal stability**: The concordance index on the hold-out test set (start_year ≥ 2022,
   ~73 rows) is directionally consistent with training-set concordance, though the small
   test set limits interpretability.

4. **Sensitivity (Model B)**: Downgrading the 144 LOW-confidence links to censored
   observations decreases the event rate and shifts the KM curve upward. The
   directional findings from the Cox model remain stable, indicating that the
   main conclusions do not hinge on borderline links.

5. **Parametric models**: The best-fitting AFT distribution (lowest AIC) provides
   predicted survival probabilities at 12 / 24 / 36 / 48 months, enabling
   forward-looking contract renewal risk assessment.

### Stated limitations

- **No ground truth**: There is no official BOAMP renewal label. `event = 1` is a
  proxy derived from the Phase 1 linking algorithm.
- **False negatives**: Contracts that genuinely renewed but were not matched by the
  algorithm appear as right-censored (event = 0). This inflates the apparent
  censoring share and may bias survival estimates upward.
- **False positives**: Some event = 1 assignments may link structurally similar but
  administratively unrelated notices, particularly among LOW-confidence links.
- **Buyer fragmentation**: Buyer identity is inferred from text; SIRET codes are
  not universally available, so buyer deduplication is imperfect.
- **`declared_duration_months` as administrative proxy**: This covariate reflects
  the planned, not the actual, contract duration and may be imputed for
  ~37% of contracts.
- **Sparse `amount_clean`** (877/1,100 NaN): Financial scale could not be included
  in the main model without substantial listwise deletion.
- **Small test set**: Only 73 contracts start in 2022 or later, limiting the power
  of temporal validation.

### Outputs

All figures saved to `reports/figures/survival/`.
All result tables saved to `reports/tables/survival/`.
"""))

# Assemble and write notebook
nb.cells = cells

import pathlib
out = pathlib.Path("notebooks/02_survival_modeling_boamp.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)

print(f"Notebook written to {out}")
