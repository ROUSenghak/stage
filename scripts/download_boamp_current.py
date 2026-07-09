from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import RAW_CURRENT, PROCESSED_CURRENT, TABLES_DATA, append_run_log, ensure_dirs, utc_now, write_json
from utils import BOAMP_API, DIGITAL_CPV_PREFIXES, PDL_DEPARTMENTS, boamp_get, extract_boamp_features, extract_cpv_codes, is_digital, parse_donnees

PAGE_SIZE = 100
MAX_OFFSET = 9_900
SLEEP_BETWEEN_PAGES = 0.2


def digital_pdl_where(start_date: str, end_date: str, departments: list[str], cpv_prefixes: tuple[str, ...]) -> str:
    deps = ",".join(f'"{d}"' for d in departments)
    likes = []
    for prefix in cpv_prefixes:
        likes.append(f'donnees LIKE "\\"PRINCIPAL\\": \\"{prefix}*"')
        likes.append(f'donnees LIKE "cpv\\", \\"#text\\": \\"{prefix}*"')
    return (
        f"code_departement IN ({deps}) "
        f"AND dateparution >= date'{start_date}' "
        f"AND dateparution <= date'{end_date}' "
        f"AND ({' OR '.join(likes)})"
    )


def year_bounds(year: int, start: pd.Timestamp, end: pd.Timestamp) -> tuple[str, str] | None:
    lo = max(start, pd.Timestamp(f"{year}-01-01"))
    hi = min(end, pd.Timestamp(f"{year}-12-31"))
    if lo > hi:
        return None
    return lo.date().isoformat(), hi.date().isoformat()


def stable_notice_key(record: dict) -> str:
    return str(record.get("idweb") or record.get("id") or record.get("url_avis") or "").strip()


def fetch_slice(start_date: str, end_date: str, out_dir: Path, departments: list[str], cpv_prefixes: tuple[str, ...]) -> tuple[list[dict], dict]:
    verified: list[dict] = []
    offset = 0
    page = 0
    warnings: list[str] = []
    schema_keys: set[str] = set()
    total_count = None

    while offset <= MAX_OFFSET:
        params = {
            "where": digital_pdl_where(start_date, end_date, departments, cpv_prefixes),
            "limit": PAGE_SIZE,
            "offset": offset,
            "order_by": "dateparution",
        }
        data = boamp_get(params)
        page += 1
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{start_date}_{end_date}_p{page:03d}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        results = data.get("results", [])
        total_count = data.get("total_count", total_count)
        for rec in results:
            schema_keys.update(rec.keys())
            if is_digital(extract_cpv_codes(parse_donnees(rec))):
                verified.append(rec)
        print(
            f"{start_date}..{end_date} p{page:03d} offset={offset:5d} "
            f"fetched={len(results):3d} verified={len(verified):5d} total={total_count}"
        )
        if len(results) < PAGE_SIZE:
            break
        if total_count and total_count > MAX_OFFSET + PAGE_SIZE:
            warnings.append(
                f"API offset cap reached for {start_date}..{end_date}; total_count={total_count}. "
                "Split by department if this appears in final metadata."
            )
        offset += PAGE_SIZE
        time.sleep(SLEEP_BETWEEN_PAGES)

    return verified, {"total_count": total_count, "pages": page, "schema_keys": sorted(schema_keys), "warnings": warnings}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2015-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    start = pd.Timestamp(args.start_date)
    end = pd.Timestamp(args.end_date)
    if start > end:
        raise SystemExit("--start-date must be before --end-date")

    all_records: list[dict] = []
    yearly_rows: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []

    for year in range(start.year, end.year + 1):
        bounds = year_bounds(year, start, end)
        if bounds is None:
            continue
        lo, hi = bounds
        print(f"\n=== BOAMP current download {lo} to {hi} ===")
        try:
            records, meta = fetch_slice(lo, hi, RAW_CURRENT / str(year), PDL_DEPARTMENTS, DIGITAL_CPV_PREFIXES)
            all_records.extend(records)
            warnings.extend(meta["warnings"])
            yearly_rows.append(
                {
                    "source": BOAMP_API,
                    "year": year,
                    "requested_start_date": lo,
                    "requested_end_date": hi,
                    "api_total_count": meta["total_count"],
                    "retained_notices": len(records),
                    "pages": meta["pages"],
                    "schema_notes": "; ".join(meta["schema_keys"][:80]),
                    "download_warnings": " | ".join(meta["warnings"]),
                }
            )
        except Exception as exc:
            msg = f"{year}: {type(exc).__name__}: {exc}"
            print(f"WARNING: {msg}", file=sys.stderr)
            errors.append(msg)

    flat_rows = [extract_boamp_features(rec) for rec in all_records]
    df = pd.DataFrame(flat_rows)
    raw_count = len(df)
    duplicate_count = 0
    if not df.empty:
        df["notice_id_original"] = df["idweb"].astype(str)
        duplicate_count = int(df.duplicated("notice_id_original").sum())
        df = df.drop_duplicates("notice_id_original", keep="last").copy()
        df["raw_source_file_group"] = "data/raw/boamp_current"

    out_csv = PROCESSED_CURRENT / "boamp_full_flat.csv"
    df.to_csv(out_csv, index=False)

    actual_min = pd.to_datetime(df["dateparution"], errors="coerce").min() if not df.empty else pd.NaT
    actual_max = pd.to_datetime(df["dateparution"], errors="coerce").max() if not df.empty else pd.NaT
    summary = pd.DataFrame(yearly_rows)
    if not summary.empty:
        summary["source"] = BOAMP_API
        summary["extraction_date"] = utc_now()
        summary["requested_date_range"] = f"{args.start_date} to {args.end_date}"
        summary["actual_date_range"] = (
            f"{actual_min.date().isoformat() if pd.notna(actual_min) else 'NA'} to "
            f"{actual_max.date().isoformat() if pd.notna(actual_max) else 'NA'}"
        )
        summary["number_of_raw_notices"] = raw_count
        summary["number_of_retained_notices"] = len(df)
        summary["duplicate_count"] = duplicate_count
    summary.to_csv(TABLES_DATA / "boamp_current_download_summary.csv", index=False)

    metadata = {
        "source": BOAMP_API,
        "scope": {
            "departments": PDL_DEPARTMENTS,
            "cpv_prefixes": list(DIGITAL_CPV_PREFIXES),
            "scope_note": "Gigalis internship scope: Pays de la Loire digital BOAMP notices.",
        },
        "extraction_date": utc_now(),
        "requested_date_range": {"start_date": args.start_date, "end_date": args.end_date},
        "actual_date_range": {
            "min_date": actual_min.date().isoformat() if pd.notna(actual_min) else None,
            "max_date": actual_max.date().isoformat() if pd.notna(actual_max) else None,
        },
        "raw_verified_records_before_deduplication": raw_count,
        "retained_records_after_deduplication": len(df),
        "duplicate_count": duplicate_count,
        "errors": errors,
        "warnings": warnings,
        "flat_output": str(out_csv.relative_to(out_csv.parents[3])),
    }
    write_json(RAW_CURRENT / "download_metadata.json", metadata)
    append_run_log(
        [
            "",
            f"## BOAMP current download - {utc_now()}",
            f"- Requested range: {args.start_date} to {args.end_date}",
            f"- Retained notices: {len(df)}",
            f"- Actual range: {metadata['actual_date_range']}",
            f"- Duplicate count: {duplicate_count}",
            f"- Errors: {errors or 'none'}",
        ]
    )
    print("\n=== Current BOAMP download summary ===")
    print(f"Raw verified records before deduplication: {raw_count}")
    print(f"Retained records after deduplication     : {len(df)}")
    print(f"Actual date range                        : {metadata['actual_date_range']}")
    print(f"Saved                                    : {out_csv}")


if __name__ == "__main__":
    main()
