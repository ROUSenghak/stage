"""TASK 5 — Scientific question of the week: reliability of the declared
contract duration in BOAMP data.

5.1  Distribution of declared durations (histogram + box plot) and flags for
     suspicious values: <= 0, > 120 months, round-number clustering
     (12/24/36/48 months exactly).
5.2  "Observed gap" between the publication of the original contract notice
     and the award date, computed *within award notices* that recall the
     original publication date (PUBLICATION_ANTERIEURE) — no extra API calls.
     NOTE: this gap measures the *procurement procedure length*, not the
     contract lifetime; the true observed duration (notification -> renewal)
     requires the Week-3 renewal linking and is explicitly out of Week-1
     scope. The discrepancy with the declared duration is still informative:
     it shows the declared duration cannot be validated from BOAMP alone.
5.3  One-paragraph conclusion printed at the end (reused in the report).

Outputs:
  reports/figures/duration_hist.png
  reports/figures/duration_box.png
  stats printed to stdout
"""

import matplotlib
matplotlib.use("Agg")  # headless environment: render to files only

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from utils import PROCESSED_DIR, FIGURES_DIR

ROUND_VALUES = (12, 24, 36, 48)  # whole-year durations suggesting coarse input


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PROCESSED_DIR / "boamp_sample_flat.csv")

    # ---- 5.1 distribution of declared durations ---------------------------
    dur = df["duration_months"].dropna()
    print("=== 5.1 Declared duration (BOAMP, months) ===")
    print(f"declared on {len(dur)}/{len(df)} notices ({len(dur)/len(df):.1%})")
    print(dur.describe().to_string())

    flags = {
        "duration <= 0": int((dur <= 0).sum()),
        "duration > 120 months": int((dur > 120).sum()),
        "exactly 12/24/36/48": int(dur.isin(ROUND_VALUES).sum()),
        "any whole-year multiple (12k)": int((dur % 12 == 0).sum()),
    }
    print("\nSuspicious-value flags:")
    for label, count in flags.items():
        print(f"  {label}: {count} ({count/len(dur):.1%})")

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.histplot(dur, bins=range(0, int(dur.max()) + 6, 3), ax=ax)
    for val in ROUND_VALUES:  # mark the whole-year spikes
        ax.axvline(val, color="red", linestyle=":", alpha=0.6)
    ax.set(title="Declared contract duration — BOAMP digital contracts PdL "
                 "(red lines: 12/24/36/48 months)",
           xlabel="duration (months)", ylabel="notices")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "duration_hist.png", dpi=150)

    fig, ax = plt.subplots(figsize=(8, 2.4))
    sns.boxplot(x=dur, ax=ax)
    ax.set(title="Declared contract duration — box plot",
           xlabel="duration (months)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "duration_box.png", dpi=150)
    print(f"\nFigures saved to {FIGURES_DIR}")

    # ---- 5.2 observed procedure gap vs declared duration ------------------
    print("\n=== 5.2 Observed gap (original publication -> award) ===")
    both = df[df["date_attribution"].notna()
              & df["date_publication_anterieure"].notna()].copy()
    both["gap_months"] = (
        (pd.to_datetime(both["date_attribution"], errors="coerce")
         - pd.to_datetime(both["date_publication_anterieure"], errors="coerce"))
        .dt.days / 30.44)
    both = both[both["gap_months"].notna() & (both["gap_months"] >= 0)]
    print(f"award notices with both dates: {len(both)}/"
          f"{(df.nature == 'ATTRIBUTION').sum()} attributions")
    print(both["gap_months"].describe().to_string())

    overlap = both[both["duration_months"].notna()]
    print(f"\nrecords with BOTH observed gap AND declared duration: "
          f"{len(overlap)}")
    if len(overlap):
        overlap = overlap.assign(
            discrepancy=overlap["gap_months"] - overlap["duration_months"])
        print(overlap[["gap_months", "duration_months", "discrepancy"]]
              .describe().to_string())

    # ---- 5.3 conclusion ----------------------------------------------------
    pct_round = dur.isin(ROUND_VALUES).mean()
    pct_year = (dur % 12 == 0).mean()
    conclusion = (
        f"CONCLUSION (5.3): The declared duration is missing on "
        f"{1 - len(dur)/len(df):.0%} of BOAMP notices (it is essentially a "
        f"contract-notice field: award notices almost never carry it), and "
        f"where present it is coarse: {pct_round:.0%} of values are exactly "
        f"12, 24, 36 or 48 months and {pct_year:.0%} are whole-year "
        f"multiples, i.e. buyers declare an administrative maximum (often "
        f"base period + renewals) rather than an expected lifetime. The "
        f"only gap observable inside BOAMP (original publication -> award, "
        f"median {both['gap_months'].median():.1f} months on {len(both)} "
        f"pairs) measures the procurement procedure, not the contract life, "
        f"so the declared duration cannot be validated against an observed "
        f"one within BOAMP alone. Recommendation: do NOT use the declared "
        f"duration as the survival target; build the target as the observed "
        f"time between successive notices of the same buyer/segment (Week-3 "
        f"renewal linking), keep the declared duration as a covariate / "
        f"prior for the renewal search window (declared duration ± 6 "
        f"months), and cross-check it against DECP's mandatory dureeMois "
        f"where a BOAMP-DECP match exists."
    )
    print("\n" + conclusion)


if __name__ == "__main__":
    main()
