"""run_all.py — Orchestrator for the SIREN enrichment pipeline.

Usage
-----
  python buyer_siren_enrichment/run_all.py            # runs all 7 steps
  python buyer_siren_enrichment/run_all.py --steps 1,2,3  # selected steps only

Steps
-----
  1  Build unique buyer table
  2  Query API Recherche d'Entreprises (cached)
  3  Score + classify + build enriched buyer table
  4  Join enrichment back to BOAMP dataset
  5  Quality / diagnostic reports
  6  Re-run Jaccard renewal linking with buyer_key_enriched
  7  Baseline vs enriched comparison + phase2 annotation
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENRICH_DIR = ROOT / "buyer_siren_enrichment"

# Ensure scripts directory is importable
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ENRICH_DIR))

LOG_FILE = ENRICH_DIR / "logs" / "run_all.log"

STEPS = {
    1: ("step1_build_unique_buyers", "Build unique buyer table"),
    2: ("step2_api_enrich",          "Query API + build candidates table"),
    3: ("step3_score_classify",      "Score, classify, buyer_key_enriched"),
    4: ("step4_join_to_boamp",       "Join enrichment to BOAMP dataset"),
    5: ("step5_quality_report",      "Quality + diagnostic reports"),
    6: ("step6_renewal_enriched",    "Renewal linking with enriched key"),
    7: ("step7_compare",             "Baseline vs enriched comparison"),
}


def _setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def run_step(step_num: int) -> bool:
    module_name, desc = STEPS[step_num]
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {desc}")
    print(f"{'='*60}")
    logging.info("Starting step %d: %s", step_num, desc)
    t0 = time.time()
    try:
        mod = importlib.import_module(module_name)
        mod.main()
        elapsed = time.time() - t0
        print(f"\n✓ Step {step_num} completed in {elapsed:.1f}s")
        logging.info("Step %d completed in %.1fs", step_num, elapsed)
        return True
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"\n✗ Step {step_num} FAILED after {elapsed:.1f}s: {exc}")
        logging.error("Step %d failed: %s", step_num, exc, exc_info=True)
        return False


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(description="SIREN enrichment pipeline")
    parser.add_argument(
        "--steps",
        default=",".join(str(k) for k in STEPS),
        help="Comma-separated list of steps to run (default: all)",
    )
    args = parser.parse_args()

    selected = [int(s.strip()) for s in args.steps.split(",") if s.strip()]
    invalid  = [s for s in selected if s not in STEPS]
    if invalid:
        print(f"Unknown steps: {invalid}. Valid steps: {list(STEPS.keys())}")
        sys.exit(1)

    print(f"Running steps: {selected}")
    t_total = time.time()
    failures = []

    for step_num in sorted(selected):
        ok = run_step(step_num)
        if not ok:
            failures.append(step_num)
            print(f"\nStep {step_num} failed. Stopping pipeline.")
            break

    elapsed_total = time.time() - t_total
    print(f"\n{'='*60}")
    if failures:
        print(f"Pipeline stopped at step {failures[0]} after {elapsed_total:.1f}s")
        sys.exit(1)
    else:
        print(f"All steps completed successfully in {elapsed_total:.1f}s")
        print(f"Log: {LOG_FILE}")


if __name__ == "__main__":
    main()
