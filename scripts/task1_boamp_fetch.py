"""TASK 1 — BOAMP API exploration.

Fetches a ~500-notice sample of *digital* public contracts in Pays de la Loire
(2015-2024) from the BOAMP Explore API, saves the raw JSON pages verbatim to
data/raw/boamp_sample/, then flattens the records to a CSV.

Sampling strategy
-----------------
- One API query per calendar year (server-side filter: PdL departments +
  digital-CPV pre-filter via LIKE on the nested `donnees` blob) so the sample
  is balanced across the 2015-2024 period (~50 notices/year).
- Every record is re-verified client-side (CPV principal or per-lot CPV must
  start with 48/72/32/35) because the LIKE clause is only a pre-filter.
- Within each year we keep a balanced mix of notice types (contract notices /
  award notices / others) by interleaving the three groups.

Fallback (documented per the brief): if the API is unreachable or
rate-limited, the error is logged to data/raw/boamp_sample/FETCH_ERRORS.log
and the annual BOAMP Open Data files (boamp.fr "données ouvertes") should be
downloaded manually instead.
"""

import json
import sys
import time

import pandas as pd

from utils import (
    RAW_BOAMP_DIR, PROCESSED_DIR, boamp_get, pdl_where_clause,
    parse_donnees, extract_cpv_codes, is_digital, extract_boamp_features,
)

TARGET_TOTAL = 500
PER_YEAR = 50          # 50 notices x 10 years = 500
PAGE_SIZE = 100
MAX_OFFSET = 9900      # Opendatasoft caps offset+limit at 10 000


def fetch_year(year: int) -> list[dict]:
    """Fetch and client-side-verify digital notices for one year.

    Pages through the pre-filtered results until enough verified records are
    collected (2x the per-year quota, to leave room for type balancing).
    """
    verified, offset, page = [], 0, 0
    while offset <= MAX_OFFSET and len(verified) < PER_YEAR * 2:
        params = {"where": pdl_where_clause(year), "limit": PAGE_SIZE,
                  "offset": offset, "order_by": "dateparution"}
        data = boamp_get(params)
        page += 1
        # Save the raw page verbatim BEFORE any transformation (reproducibility)
        raw_path = RAW_BOAMP_DIR / f"boamp_{year}_p{page}.json"
        raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=1))

        results = data.get("results", [])
        for rec in results:
            # client-side confirmation of the CPV filter
            if is_digital(extract_cpv_codes(parse_donnees(rec))):
                verified.append(rec)
        print(f"  {year} page {page}: {len(results)} fetched, "
              f"{len(verified)} verified digital so far "
              f"(total matching: {data.get('total_count')})")
        if len(results) < PAGE_SIZE:  # no more pages
            break
        offset += PAGE_SIZE
        time.sleep(0.5)  # politeness delay
    return verified


def balance_types(records: list[dict], quota: int) -> list[dict]:
    """Keep up to `quota` records, interleaving contract notices, award
    notices and other natures so both AAPC and attributions are represented."""
    groups = {"APPEL_OFFRE": [], "ATTRIBUTION": [], "OTHER": []}
    for rec in records:
        groups.get(rec.get("nature"), groups["OTHER"]).append(rec)
    kept, idx = [], 0
    while len(kept) < quota and any(groups.values()):
        for key in ("APPEL_OFFRE", "ATTRIBUTION", "OTHER"):
            if groups[key] and len(kept) < quota:
                kept.append(groups[key].pop(0))
        idx += 1
    return kept


def main() -> None:
    RAW_BOAMP_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    sample, errors = [], []
    for year in range(2015, 2025):
        print(f"Year {year} …")
        try:
            year_records = fetch_year(year)
        except RuntimeError as err:
            # Documented fallback: log and continue with the other years.
            errors.append(f"{year}: {err}")
            print(f"  !! API error for {year}: {err}", file=sys.stderr)
            continue
        sample.extend(balance_types(year_records, PER_YEAR))

    if errors:
        (RAW_BOAMP_DIR / "FETCH_ERRORS.log").write_text(
            "\n".join(errors)
            + "\nFallback: download annual Open Data files from boamp.fr\n")

    # Top-up: if some years yielded < 50, refill from recent years (largest volumes)
    if len(sample) < TARGET_TOTAL:
        print(f"Topping up sample ({len(sample)}/{TARGET_TOTAL}) from 2022-2024 …")
        seen = {r.get("idweb") for r in sample}
        for year in (2024, 2023, 2022):
            if len(sample) >= TARGET_TOTAL:
                break
            for rec in fetch_year(year):
                if rec.get("idweb") not in seen and len(sample) < TARGET_TOTAL:
                    sample.append(rec)
                    seen.add(rec.get("idweb"))

    sample = sample[:TARGET_TOTAL]

    # ---- Flatten to a DataFrame and report -------------------------------
    df = pd.DataFrame(extract_boamp_features(rec) for rec in sample)
    out = PROCESSED_DIR / "boamp_sample_flat.csv"
    df.to_csv(out, index=False)

    print("\n=== TASK 1 summary ===")
    print(f"Total records retrieved : {len(df)}")
    print(f"Saved flat CSV          : {out}")
    print("\nAvailable fields (columns):")
    print(list(df.columns))
    print("\nData types:")
    print(df.dtypes.to_string())
    print("\nFirst 5 rows:")
    with pd.option_context("display.max_columns", None, "display.width", 200,
                           "display.max_colwidth", 25):
        print(df.head(5))
    print("\nNotices per year:")
    print(df["dateparution"].str[:4].value_counts().sort_index().to_string())
    print("\nNotices per nature:")
    print(df["nature"].value_counts().to_string())


if __name__ == "__main__":
    main()
