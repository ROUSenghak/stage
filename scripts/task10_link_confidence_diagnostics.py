"""TASK 10 — Strict high-confidence renewal-link diagnostics.

Operationalizes the score-margin disambiguation diagnostic on top of the existing
renewal-linking outputs. It does NOT relink notices and does NOT re-run the
Sentence-Transformers pipeline: the diagnostics are a deterministic function of the
candidate pairs and the best-match links already produced by the linking notebook.

Inputs
------
  boamp_renewal_linking_quality/outputs/boamp_renewal_candidates.csv
  boamp_renewal_linking_quality/outputs/boamp_renewal_links.csv

Outputs
-------
  boamp_renewal_linking_quality/outputs/boamp_renewal_links.csv          (augmented in place)
  boamp_renewal_linking_quality/outputs/boamp_link_confidence_diagnostics.csv

Notes
-----
The strict high-confidence definition is NOT a new ground truth. It is a conservative
sensitivity definition requiring both a high absolute composite score and a clear margin
over the second-best candidate.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from link_confidence import DIAGNOSTIC_COLUMNS, compute_link_confidence, format_summary
from utils import ROOT

OUTPUTS = ROOT / "boamp_renewal_linking_quality" / "outputs"
CANDIDATES_CSV = OUTPUTS / "boamp_renewal_candidates.csv"
LINKS_CSV = OUTPUTS / "boamp_renewal_links.csv"
DIAGNOSTICS_CSV = OUTPUTS / "boamp_link_confidence_diagnostics.csv"


def main() -> None:
    for path in (CANDIDATES_CSV, LINKS_CSV):
        if not path.exists():
            raise SystemExit(
                f"Required input not found: {path}\n"
                "Run the renewal-linking notebook first."
            )

    candidates = pd.read_csv(CANDIDATES_CSV)
    links = pd.read_csv(LINKS_CSV)

    n_rows_before = len(links)
    n_events_before = int(pd.to_numeric(links["event"], errors="coerce").fillna(0).sum())

    # Idempotent: drop any previously-added diagnostic columns before recomputing.
    links = links.drop(columns=[c for c in DIAGNOSTIC_COLUMNS if c in links.columns])

    links_aug, diagnostics, stats = compute_link_confidence(candidates, links)

    # Guard rails — diagnostics must be purely additive.
    assert len(links_aug) == n_rows_before, "row count changed"
    assert (
        int(links_aug["event"].sum()) == n_events_before
    ), "baseline event count changed"

    links_aug.to_csv(LINKS_CSV, index=False)
    diagnostics.to_csv(DIAGNOSTICS_CSV, index=False)

    print(format_summary(stats))
    print(f"\nRows                 : {len(links_aug):,} (unchanged)")
    print(f"Events (baseline)    : {n_events_before:,} (unchanged)")
    print(f"New columns          : {DIAGNOSTIC_COLUMNS}")
    print(f"Augmented links      : {LINKS_CSV}")
    print(f"Diagnostics CSV      : {DIAGNOSTICS_CSV}")


if __name__ == "__main__":
    main()
