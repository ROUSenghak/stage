"""TASK 1b — Full BOAMP download (no sampling cap).

Fetches ALL digital public contracts in Pays de la Loire for 2015-2024
from the BOAMP Explore API. Unlike task1 (50 notices/year sample), this
script pages through every result for each year.

Volume check (2026-06-15):
  2015: 2599 | 2016: 3114 | 2017: 3362 | 2018: 3370 | 2019: 3689
  2020: 3217 | 2021: 3617 | 2022: 3505 | 2023: 3691 | 2024: 4198
  Total (pre-filter): ~34 362 records across 10 years.
  After client-side CPV verification: expect ~28 000–32 000.

API constraint: Opendatasoft caps offset + limit at 10 000. Each year
stays well below that limit, so one paginated query per year is enough.
If a future year exceeds 10 000, split by department (see comment below).

Outputs
-------
  data/raw/boamp_full/<year>_p<page>.json   raw pages (reproducibility)
  data/processed/boamp_full_flat.csv        one row per verified record
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

# project root so we can import utils from scripts/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    PROCESSED_DIR,
    boamp_get,
    pdl_where_clause,
    parse_donnees,
    extract_cpv_codes,
    is_digital,
    extract_boamp_features,
)

RAW_FULL_DIR = ROOT / "data" / "raw" / "boamp_full"
PAGE_SIZE = 100
# Opendatasoft hard cap: offset + limit <= 10 000
MAX_OFFSET = 9_900
SLEEP_BETWEEN_PAGES = 0.35   # seconds — polite but not slow


def fetch_year_full(year: int) -> list[dict]:
    """Fetch and client-side-verify ALL digital notices for one year."""
    verified: list[dict] = []
    offset = 0
    page = 0

    while offset <= MAX_OFFSET:
        params = {
            "where": pdl_where_clause(year),
            "limit": PAGE_SIZE,
            "offset": offset,
            "order_by": "dateparution",
        }
        data = boamp_get(params)
        page += 1

        raw_path = RAW_FULL_DIR / f"{year}_p{page}.json"
        raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=1))

        results = data.get("results", [])
        total = data.get("total_count", 0)

        before = len(verified)
        for rec in results:
            if is_digital(extract_cpv_codes(parse_donnees(rec))):
                verified.append(rec)
        after = len(verified)

        print(
            f"  {year} p{page:03d}  offset={offset:5d}  "
            f"fetched={len(results):3d}  verified this page={after - before:3d}  "
            f"running total={after}  (API total_count={total})"
        )

        if len(results) < PAGE_SIZE:
            break  # last page

        if total > MAX_OFFSET + PAGE_SIZE:
            # Safety warning — should not happen for current volumes
            print(
                f"  WARNING: year {year} has {total} records but the API caps at "
                f"{MAX_OFFSET + PAGE_SIZE}. Records beyond that offset are lost. "
                "Split by department to recover them.",
                file=sys.stderr,
            )

        offset += PAGE_SIZE
        time.sleep(SLEEP_BETWEEN_PAGES)

    return verified


def main() -> None:
    RAW_FULL_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    errors: list[str] = []

    for year in range(2015, 2025):
        print(f"\n=== Year {year} ===")
        try:
            records = fetch_year_full(year)
            all_records.extend(records)
            print(f"  -> {len(records)} verified records for {year}")
        except RuntimeError as err:
            errors.append(f"{year}: {err}")
            print(f"  !! API error for {year}: {err}", file=sys.stderr)

    if errors:
        err_path = RAW_FULL_DIR / "FETCH_ERRORS.log"
        err_path.write_text(
            "\n".join(errors)
            + "\nFallback: download annual Open Data JSON files from boamp.fr\n"
        )
        print(f"\nErrors logged to {err_path}")

    print(f"\nFlattening {len(all_records)} records …")
    df = pd.DataFrame(extract_boamp_features(rec) for rec in all_records)

    out = PROCESSED_DIR / "boamp_full_flat.csv"
    df.to_csv(out, index=False)

    print("\n=== TASK 1b summary ===")
    print(f"Total records fetched   : {len(df)}")
    print(f"Saved to                : {out}")
    print("\nRecords per year:")
    print(df["dateparution"].str[:4].value_counts().sort_index().to_string())
    print("\nRecords per notice type:")
    print(df["nature"].value_counts().to_string())
    print(f"\nDuration filled: {df['duration_months'].notna().sum()}/{len(df)} "
          f"({df['duration_months'].notna().mean()*100:.1f}%)")
    print(f"Amount filled:   {df['amount_eur'].notna().sum()}/{len(df)} "
          f"({df['amount_eur'].notna().mean()*100:.1f}%)")
    print(f"SIRET filled:    {df['buyer_siret'].notna().sum()}/{len(df)} "
          f"({df['buyer_siret'].notna().mean()*100:.1f}%)")


if __name__ == "__main__":
    main()
