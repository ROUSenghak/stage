"""Strict high-confidence renewal-link diagnostics (score-margin based).

Shared, single-source-of-truth logic used by both:
  - the BOAMP renewal-linking notebook
    (boamp_renewal_linking_quality/boamp_renewal_linking_eda_preprocessing.ipynb), and
  - the runnable regeneration script (scripts/task10_link_confidence_diagnostics.py).

The current linking algorithm keeps, for each eligible source contract, the single
candidate with the highest composite score. This module operationalizes the
score-disambiguation diagnostic already discussed in the report:

    score_margin = best_composite_score - second_best_composite_score

and defines a conservative ``high_confidence_strict`` flag requiring BOTH a high
absolute composite score AND a clear margin over the second-best candidate.

IMPORTANT — interpretation
--------------------------
The strict high-confidence definition is NOT a new ground truth. It is a conservative
sensitivity definition requiring both a high absolute score and a clear margin over the
second-best candidate. It is used to bound, not to correct, the renewal-event estimate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Strict-confidence thresholds (kept here so notebook and script never drift).
HIGH_CONFIDENCE_MIN_COMPOSITE = 0.70
HIGH_CONFIDENCE_MIN_MARGIN = 0.05

# Columns added to the renewal-link output and the Phase 2 handoff.
DIAGNOSTIC_COLUMNS = [
    "best_composite_score",
    "second_best_composite_score",
    "score_margin",
    "n_candidates_for_source",
    "single_candidate_match",
    "high_confidence_strict",
]


def _per_source_margin(candidates_df: pd.DataFrame) -> pd.DataFrame:
    """Best / second-best composite score and candidate count per source AO.

    Mirrors the grouping in ``data.ipynb::save_score_margin``: for each ``src_idweb``
    sort the composite scores descending and take the top two.
    """
    scores = pd.to_numeric(candidates_df["composite_score"], errors="coerce")
    work = pd.DataFrame(
        {"src_idweb": candidates_df["src_idweb"].astype(str), "composite_score": scores}
    ).dropna(subset=["composite_score"])

    rows = []
    for src_idweb, grp in work.groupby("src_idweb", sort=False):
        ordered = grp["composite_score"].sort_values(ascending=False).to_numpy()
        best = float(ordered[0])
        second = float(ordered[1]) if len(ordered) >= 2 else np.nan
        rows.append(
            {
                "src_idweb": src_idweb,
                "best_composite_score": best,
                "second_best_composite_score": second,
                "score_margin": (best - second) if len(ordered) >= 2 else np.nan,
                "n_candidates_for_source": int(len(ordered)),
            }
        )
    return pd.DataFrame(rows)


def compute_link_confidence(
    candidates_df: pd.DataFrame, links_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Augment renewal links with strict-confidence diagnostics.

    Parameters
    ----------
    candidates_df : the post-filter candidate pairs (one row per source x candidate;
        ``boamp_renewal_candidates.csv``). Must contain ``src_idweb`` and
        ``composite_score``.
    links_df : one row per eligible source AO (``boamp_renewal_links.csv``). Must
        contain ``contract_id``, ``event`` and ``composite_score``.

    Returns
    -------
    (links_aug, diagnostics_df, stats)
        ``links_aug`` is ``links_df`` plus the six DIAGNOSTIC_COLUMNS.
        ``diagnostics_df`` is the standalone diagnostics table.
        ``stats`` is a dict of summary counts/shares.
    """
    links = links_df.copy()

    # Stable join key: strip the "BOAMP:" prefix to recover the raw idweb.
    links["_idweb"] = links["contract_id"].astype(str).str.replace(
        "BOAMP:", "", regex=False
    )

    margins = _per_source_margin(candidates_df).set_index("src_idweb")
    links = links.merge(margins, left_on="_idweb", right_index=True, how="left")

    event = pd.to_numeric(links["event"], errors="coerce").fillna(0).astype(int)
    composite = pd.to_numeric(links["composite_score"], errors="coerce")

    # event == 0 rows were never linked: no candidate diagnostics apply.
    censored = event == 0
    for col in ("best_composite_score", "second_best_composite_score", "score_margin"):
        links.loc[censored, col] = np.nan
    links["n_candidates_for_source"] = (
        links["n_candidates_for_source"].where(~censored, 0).fillna(0).astype(int)
    )

    links["single_candidate_match"] = (event == 1) & (
        links["n_candidates_for_source"] == 1
    )

    # NaN margin (single candidate) compares False, so single-candidate links are never
    # auto-marked strict — by design.
    margin = pd.to_numeric(links["score_margin"], errors="coerce")
    links["high_confidence_strict"] = (
        (event == 1)
        & (composite >= HIGH_CONFIDENCE_MIN_COMPOSITE)
        & (margin >= HIGH_CONFIDENCE_MIN_MARGIN)
    )

    links = links.drop(columns=["_idweb"])

    # ── Standalone diagnostics table ──────────────────────────────────────────────
    diag_cols = [
        "contract_id",
        "renewal_contract_id",
        "event",
        "composite_score",
        "best_composite_score",
        "second_best_composite_score",
        "score_margin",
        "n_candidates_for_source",
        "single_candidate_match",
        "high_confidence_strict",
        "text_similarity",
        "cpv_match_score",
        "temporal_score",
        "declared_duration_months",
        "observed_duration_months",
    ]
    diagnostics_df = links[[c for c in diag_cols if c in links.columns]].copy()

    stats = _summary_stats(links)
    return links, diagnostics_df, stats


def _summary_stats(links: pd.DataFrame) -> dict:
    """Summary counts/shares for the strict-confidence diagnostic (requirement 7)."""
    event = pd.to_numeric(links["event"], errors="coerce").fillna(0).astype(int)
    composite = pd.to_numeric(links["composite_score"], errors="coerce")
    margin = pd.to_numeric(links["score_margin"], errors="coerce")
    n_cand = pd.to_numeric(links["n_candidates_for_source"], errors="coerce").fillna(0)

    e1 = event == 1
    n_e1 = int(e1.sum())

    high_comp = e1 & (composite >= HIGH_CONFIDENCE_MIN_COMPOSITE)
    multi = e1 & (n_cand >= 2)
    n_multi = int(multi.sum())
    margin_ok_multi = multi & (margin >= HIGH_CONFIDENCE_MIN_MARGIN)
    ambiguous_multi = multi & (margin < HIGH_CONFIDENCE_MIN_MARGIN)
    strict = links["high_confidence_strict"].astype(bool)
    single = links["single_candidate_match"].astype(bool)

    def share(n, d):
        return round(100 * n / d, 2) if d else 0.0

    return {
        "n_event1_links": n_e1,
        "n_composite_ge_070": int(high_comp.sum()),
        "share_composite_ge_070": share(int(high_comp.sum()), n_e1),
        "n_multi_candidate": n_multi,
        "n_margin_ge_005_multi": int(margin_ok_multi.sum()),
        "share_margin_ge_005_multi": share(int(margin_ok_multi.sum()), n_multi),
        "n_high_confidence_strict": int(strict.sum()),
        "share_high_confidence_strict": share(int(strict.sum()), n_e1),
        "n_single_candidate_match": int(single.sum()),
        "n_ambiguous_margin_lt_005": int(ambiguous_multi.sum()),
    }


def format_summary(stats: dict) -> str:
    """Human-readable summary block (printed by notebook and script)."""
    s = stats
    return "\n".join(
        [
            "=" * 60,
            "  STRICT HIGH-CONFIDENCE LINK DIAGNOSTICS",
            "=" * 60,
            f"  event=1 links:                          {s['n_event1_links']:>6,}",
            f"  composite_score >= 0.70:                {s['n_composite_ge_070']:>6,}"
            f"  ({s['share_composite_ge_070']}%)",
            f"  multi-candidate links:                  {s['n_multi_candidate']:>6,}",
            f"  score_margin >= 0.05 (multi-candidate): {s['n_margin_ge_005_multi']:>6,}"
            f"  ({s['share_margin_ge_005_multi']}% of multi)",
            f"  high_confidence_strict:                 {s['n_high_confidence_strict']:>6,}"
            f"  ({s['share_high_confidence_strict']}% of events)",
            f"  single-candidate matches:               {s['n_single_candidate_match']:>6,}",
            f"  ambiguous (multi, margin < 0.05):       {s['n_ambiguous_margin_lt_005']:>6,}",
            "=" * 60,
            "  NOTE: high_confidence_strict is a conservative sensitivity",
            "  definition, NOT a new ground truth.",
            "=" * 60,
        ]
    )
