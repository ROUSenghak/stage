"""TASK 8 — Unified survival dataset (BOAMP + DECP).

Combines two sources into one analysis-ready dataset for Phase 3 survival
modeling:

  1. DECP survival records (task6 output) — 2018-2024 contracts.
     These are kept as-is: the Jaccard linker in task6 already built
     event/censored labels for all 3 039 DECP contracts.

  2. BOAMP supplement for the pre-DECP gap — 2015-2017 contracts.
     DECP coverage starts in 2018; this period is BOAMP-only.
     Records are loaded directly from boamp_full_survival.csv (produced
     by task_boamp_full_survival.py) and filtered to start_date < 2018.
     Using the full download (1 933 APPEL_OFFRE) rather than the stale
     500-record sample dramatically increases pre-2018 coverage.

Deduplication
  BOAMP records from 2018 onwards are excluded to avoid double-counting
  with DECP, which has mandatory and structured coverage for that period.

Outputs
-------
  data/processed/unified_survival.csv   — one row per contract
  data/processed/unified_survival_report.md
"""

from __future__ import annotations

import pandas as pd

from utils import PROCESSED_DIR

# ── Constants ────────────────────────────────────────────────────────────────

STUDY_END = pd.Timestamp("2024-12-31")
DECP_START = "2018-01-01"   # string — compared against start_date column


def normalize_cpv_div2(series: pd.Series) -> pd.Series:
    """Return CPV divisions as two-character strings across CSV dtype quirks."""
    values = series.astype("string").str.strip()
    values = values.str.replace(r"\.0$", "", regex=True)
    values = values.mask(values.isin(["", "nan", "None", "<NA>"]))
    return values.str.extract(r"(\d{2})", expand=False).fillna(values)


# ── BOAMP pre-2018 supplement ────────────────────────────────────────────────

def build_boamp_survival() -> pd.DataFrame:
    """Load pre-2018 records from boamp_full_survival.csv.

    boamp_full_survival.csv was produced by task_boamp_full_survival.py using
    the complete 1 933-notice BOAMP download. We take only records whose
    start_date falls before 2018-01-01 to avoid overlap with DECP.
    text_similarity is an internal column not needed in the unified schema.
    """
    path = PROCESSED_DIR / "boamp_full_survival.csv"
    if not path.exists():
        print(f"  WARNING: {path} not found — skipping BOAMP supplement.")
        print("  Run scripts/task_boamp_full_survival.py first.")
        return pd.DataFrame()

    boamp = pd.read_csv(path)
    pre2018 = boamp[boamp["start_date"] < DECP_START].copy()
    pre2018 = pre2018.drop(columns=["text_similarity"], errors="ignore")
    return pre2018


# ── DECP records ─────────────────────────────────────────────────────────────

def build_decp_survival(decp_clean: pd.DataFrame,
                        decp_links: pd.DataFrame) -> pd.DataFrame:
    """Convert task6 DECP renewal links to the unified schema."""

    # Enrich with buyer and taxonomy attributes from decp_clean
    attrs = decp_clean[
        ["uid", "buyer_key", "category_id", "category_label", "amount_clean"]
    ].drop_duplicates("uid")

    merged = decp_links.merge(attrs, on="uid", how="left")

    rows = []
    for _, row in merged.iterrows():
        event = int(row["event"])
        rows.append({
            "contract_id": f"DECP:{row['uid']}",
            "source": "DECP",
            "buyer_key": row.get("buyer_key"),
            "cpv_div2": row.get("cpv_div2"),
            "category_id": row.get("category_id"),
            "category_label": row.get("category_label"),
            "start_date": str(row["source_date_notification"])[:10]
            if pd.notna(row.get("source_date_notification")) else None,
            "declared_duration_months": pd.to_numeric(
                row.get("declared_duration_months"), errors="coerce"
            ),
            "event": event,
            "observed_duration_months": float(row["observed_duration_months"]),
            "amount_clean": pd.to_numeric(row.get("amount_clean"), errors="coerce"),
            "link_method": "decp_jaccard" if event == 1 else "none",
            "renewal_contract_id": f"DECP:{row['renewal_uid']}"
            if pd.notna(row.get("renewal_uid")) else None,
        })

    return pd.DataFrame(rows)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    decp_clean = pd.read_csv(PROCESSED_DIR / "decp_clean.csv", dtype=str)
    decp_links = pd.read_csv(PROCESSED_DIR / "decp_renewal_links.csv", dtype=str)

    # Numeric coercions for decp inputs
    for col in ("event", "observed_duration_months", "declared_duration_months"):
        decp_links[col] = pd.to_numeric(decp_links[col], errors="coerce")
    decp_links["event"] = decp_links["event"].fillna(0).astype(int)
    decp_clean["amount_clean"] = pd.to_numeric(decp_clean["amount_clean"], errors="coerce")

    print("Building DECP survival records …")
    decp_survival = build_decp_survival(decp_clean, decp_links)
    print(f"  {len(decp_survival)} DECP records, {decp_survival['event'].sum()} events")

    print("Loading BOAMP pre-2018 supplement from boamp_full_survival.csv …")
    boamp_survival = build_boamp_survival()
    if not boamp_survival.empty:
        print(f"  {len(boamp_survival)} BOAMP records, {int(boamp_survival['event'].sum())} events")
    else:
        print("  0 BOAMP records added")

    unified = pd.concat([decp_survival, boamp_survival], ignore_index=True)
    unified = unified[unified["observed_duration_months"] > 0].copy()
    unified["cpv_div2"] = normalize_cpv_div2(unified["cpv_div2"])
    unified = unified.sort_values("start_date").reset_index(drop=True)

    out_csv = PROCESSED_DIR / "unified_survival.csv"
    unified.to_csv(out_csv, index=False)

    # ── Summary ──────────────────────────────────────────────────────────────
    n = len(unified)
    n_events = int(unified["event"].sum())
    n_decp = int((unified["source"] == "DECP").sum())
    n_boamp = int((unified["source"] == "BOAMP").sum())
    event_rate = round(100 * n_events / n, 1) if n else 0.0

    print("\n=== TASK 8 summary ===")
    print(f"Total contracts : {n}")
    print(f"  DECP (2018–2024) : {n_decp}")
    print(f"  BOAMP (2015–2017): {n_boamp}")
    print(f"Events (renewals)  : {n_events}  ({event_rate}%)")
    print(f"Right-censored     : {n - n_events}  ({round(100 - event_rate, 1)}%)")
    print("\nLink method breakdown:")
    print(unified["link_method"].value_counts().to_string())
    print("\nEvents by CPV segment:")
    seg = (
        unified.groupby("cpv_div2", as_index=False)
        .agg(n=("contract_id", "count"), events=("event", "sum"))
    )
    seg["event_rate_%"] = (100 * seg["events"] / seg["n"]).round(1)
    print(seg.to_string(index=False))
    print(f"\nSaved: {out_csv}")

    # ── Markdown report ───────────────────────────────────────────────────────
    report_lines = [
        "# Task 8 – Unified Survival Dataset",
        "",
        "## Composition",
        f"| Source | Contracts | Events | Event rate |",
        f"|--------|-----------|--------|------------|",
        f"| DECP (2018–2024) | {n_decp} | {decp_survival['event'].sum()} | "
        f"{round(100*decp_survival['event'].sum()/len(decp_survival),1) if len(decp_survival) else 0}% |",
    ]
    if not boamp_survival.empty:
        report_lines.append(
            f"| BOAMP (2015–2017) | {n_boamp} | {boamp_survival['event'].sum()} | "
            f"{round(100*boamp_survival['event'].sum()/len(boamp_survival),1)}% |"
        )
    report_lines += [
        f"| **Total** | **{n}** | **{n_events}** | **{event_rate}%** |",
        "",
        "## Why censoring is expected",
        "55% of DECP contracts started in 2022 or later. With typical 48-month",
        "durations, their renewals would fall after the study end (Dec 2024).",
        "Survival analysis handles this correctly via right-censoring — censored",
        "observations are valid data, not missing data.",
        "",
        "## Linking methods",
        "- `decp_jaccard`: Jaccard similarity ≥ 0.30, time window ± 6 months (task6).",
        "- `boamp_jaccard`: Jaccard similarity ≥ 0.20, time window ± 6 months (task_boamp_full_survival).",
        "- `none`: no renewal found — contract treated as right-censored at study end.",
        "- `annonce_lie` was used to refine BOAMP start dates (award date > pub date).",
        "",
        "## Known limitations",
        "1. BOAMP buyer_key is name-based for ~91% of records (SIRET coverage ~9%).",
        "   Name normalization may split one real buyer into multiple keys.",
        "2. Cross-source deduplication (BOAMP post-2018 vs DECP) is handled by",
        "   excluding BOAMP notices from 2018 onwards. Some pre-2018 DECP records",
        "   may still overlap if DECP backfilling extended before 2018.",
        "3. The event rate (~8%) reflects the observation window, not a data defect.",
        "   For survival modeling, all rows (event=0 and event=1) contribute.",
    ]

    report_path = PROCESSED_DIR / "unified_survival_report.md"
    report_path.write_text("\n".join(report_lines))
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    main()
