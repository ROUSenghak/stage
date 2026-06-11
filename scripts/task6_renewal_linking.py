"""TASK 6 — Renewal linking prototype (Week 3 core step).

Builds a contract-level dataset with observed or censored durations by linking each
DECP contract to a plausible later renewal from the same buyer and CPV segment.

Matching logic (simple, reproducible baseline)
---------------------------------------------
1) Same buyer (`acheteur_id`) and same CPV division (first 2 digits of codeCPV).
2) Candidate must be later in time than the source contract.
3) Temporal proximity around the declared duration: expected +/- 6 months.
4) Minimum textual similarity on the contract object (token Jaccard).

Outputs
-------
- data/processed/decp_renewal_links.csv
    one row per contract with event flag and observed/censored duration.
- data/processed/decp_renewal_linking_stats.csv
    linking rates overall and by CPV division.
- data/processed/decp_renewal_linking_report.md
    short interpretation for Week-3 report integration.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pandas as pd

from utils import PROCESSED_DIR

WINDOW_MONTHS = 6.0
MIN_TEXT_SIM = 0.30
MIN_DURATION = 1.0
MAX_DURATION = 120.0
STUDY_END = pd.Timestamp("2024-12-31")


@dataclass
class LinkResult:
    renewal_uid: str | None
    event: int
    observed_months: float
    gap_months: float | None
    expected_months: float
    text_similarity: float | None
    score: float | None


def month_diff(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return (end - start).days / 30.44


def normalize_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def token_set(value: str) -> set[str]:
    tokens = [t for t in normalize_text(value).split(" ") if len(t) >= 3]
    return set(tokens)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def expected_duration_months(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 24.0
    if math.isnan(v):
        v = 24.0
    return max(MIN_DURATION, min(MAX_DURATION, v))


def choose_candidate(source: pd.Series, candidates: pd.DataFrame) -> LinkResult:
    start = source["start_date"]
    expected = expected_duration_months(source.get("dureeMois"))
    low = max(MIN_DURATION, expected - WINDOW_MONTHS)
    high = expected + WINDOW_MONTHS

    valid = candidates[candidates["start_date"] > start].copy()
    if valid.empty:
        return LinkResult(None, 0, month_diff(start, STUDY_END), None, expected, None, None)

    valid["gap_months"] = valid["start_date"].map(lambda d: month_diff(start, d))
    valid = valid[(valid["gap_months"] >= low) & (valid["gap_months"] <= high)]
    if valid.empty:
        return LinkResult(None, 0, month_diff(start, STUDY_END), None, expected, None, None)

    source_tokens = source["object_tokens"]
    valid["text_similarity"] = valid["object_tokens"].map(lambda t: jaccard(source_tokens, t))
    valid = valid[valid["text_similarity"] >= MIN_TEXT_SIM]
    if valid.empty:
        return LinkResult(None, 0, month_diff(start, STUDY_END), None, expected, None, None)

    # Composite score: mostly semantic continuity, secondarily temporal proximity.
    valid["time_fit"] = 1.0 - (valid["gap_months"] - expected).abs() / WINDOW_MONTHS
    valid["time_fit"] = valid["time_fit"].clip(lower=0.0, upper=1.0)
    valid["score"] = 0.7 * valid["text_similarity"] + 0.3 * valid["time_fit"]

    best = valid.sort_values(["score", "gap_months"], ascending=[False, True]).iloc[0]
    return LinkResult(
        renewal_uid=str(best["uid"]),
        event=1,
        observed_months=float(best["gap_months"]),
        gap_months=float(best["gap_months"]),
        expected_months=expected,
        text_similarity=float(best["text_similarity"]),
        score=float(best["score"]),
    )


def main() -> None:
    df = pd.read_csv(PROCESSED_DIR / "decp_sample_flat.csv", dtype={"acheteur_id": str, "uid": str})

    df["start_date"] = pd.to_datetime(df["dateNotification"], errors="coerce")
    df = df[df["start_date"].notna()].copy()
    df = df[df["start_date"] <= STUDY_END].copy()

    cpv_clean = df["codeCPV"].astype(str).str.split("-").str[0]
    df["cpv_div2"] = cpv_clean.str[:2]
    df["object_tokens"] = df["objet"].map(token_set)

    # Grouping by buyer + CPV division keeps candidate sets small and coherent.
    groups = df.groupby(["acheteur_id", "cpv_div2"], dropna=False, sort=False)
    rows = []

    for (_, _), grp in groups:
        grp = grp.sort_values("start_date")
        for _, source in grp.iterrows():
            result = choose_candidate(source, grp)
            rows.append(
                {
                    "uid": source["uid"],
                    "acheteur_id": source["acheteur_id"],
                    "cpv_div2": source["cpv_div2"],
                    "source_date_notification": source["start_date"].date().isoformat(),
                    "declared_duration_months": expected_duration_months(source.get("dureeMois")),
                    "renewal_uid": result.renewal_uid,
                    "event": result.event,
                    "observed_duration_months": round(result.observed_months, 2),
                    "gap_months": round(result.gap_months, 2) if result.gap_months is not None else None,
                    "text_similarity": round(result.text_similarity, 3) if result.text_similarity is not None else None,
                    "match_score": round(result.score, 3) if result.score is not None else None,
                    "is_censored": int(result.event == 0),
                    "censoring_date": STUDY_END.date().isoformat() if result.event == 0 else None,
                }
            )

    links = pd.DataFrame(rows)

    # Durations cannot be negative in survival datasets.
    links = links[links["observed_duration_months"] >= 0].copy()

    out_links = PROCESSED_DIR / "decp_renewal_links.csv"
    links.to_csv(out_links, index=False)

    overall = {
        "scope": "overall",
        "n_contracts": len(links),
        "n_events": int(links["event"].sum()),
        "linking_rate_pct": round(100 * links["event"].mean(), 2),
        "median_observed_duration_months": round(float(links["observed_duration_months"].median()), 2),
        "median_event_duration_months": round(float(links.loc[links["event"] == 1, "observed_duration_months"].median()), 2)
        if (links["event"] == 1).any()
        else None,
    }

    by_segment = (
        links.groupby("cpv_div2", as_index=False)
        .agg(
            n_contracts=("uid", "count"),
            n_events=("event", "sum"),
            median_observed_duration_months=("observed_duration_months", "median"),
        )
    )
    by_segment["linking_rate_pct"] = (100 * by_segment["n_events"] / by_segment["n_contracts"]).round(2)
    by_segment = by_segment[["cpv_div2", "n_contracts", "n_events", "linking_rate_pct", "median_observed_duration_months"]]

    stats = pd.concat([pd.DataFrame([overall]), by_segment.rename(columns={"cpv_div2": "scope"})], ignore_index=True)
    out_stats = PROCESSED_DIR / "decp_renewal_linking_stats.csv"
    stats.to_csv(out_stats, index=False)

    report = (
        "# DECP renewal linking report (prototype)\n\n"
        f"- Contracts analyzed: {overall['n_contracts']}\n"
        f"- Linked renewals (events): {overall['n_events']}\n"
        f"- Linking rate: {overall['linking_rate_pct']}%\n"
        f"- Median observed duration (all): {overall['median_observed_duration_months']} months\n"
        f"- Median observed duration (events only): {overall['median_event_duration_months']} months\n\n"
        "## Matching rules\n"
        "1. Same buyer (`acheteur_id`) and same CPV division (`codeCPV[:2]`).\n"
        "2. Candidate appears later in time (`dateNotification`).\n"
        "3. Time window around declared duration (`dureeMois ± 6 months`).\n"
        "4. Object similarity >= 0.30 (token Jaccard).\n\n"
        "## Notes\n"
        "- This is a reproducible baseline for Week 3, not the final production linker.\n"
        "- Next iteration should evaluate precision/recall on a manually reviewed sample and test stricter segmenting (CPV4) and one-to-one matching constraints.\n"
    )
    out_report = PROCESSED_DIR / "decp_renewal_linking_report.md"
    out_report.write_text(report)

    print("=== TASK 6 summary ===")
    print(f"Saved links : {out_links}")
    print(f"Saved stats : {out_stats}")
    print(f"Saved report: {out_report}")
    print("\nOverall:")
    print(pd.DataFrame([overall]).to_string(index=False))
    print("\nBy CPV division:")
    print(by_segment.to_string(index=False))


if __name__ == "__main__":
    main()
