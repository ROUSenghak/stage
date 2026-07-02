# BOAMP Raw Record Extraction — Note

## Why this file exists

The full BOAMP open-data export for Pays de la Loire (2015–2024, digital CPV divisions) is
stored locally as ~465 JSON files totalling approximately 513 MB across two directories:

- `data/raw/boamp_full/` — 348 files, ~384 MB (authoritative full export)
- `data/raw/boamp_sample/` — 117 files, ~129 MB (subset used for development)

This file is too large to include in a shared repository or to process in full for a
150-row validation exercise. Instead, the script
`event_validation/extract_boamp_validation_records_from_json.py`
extracted only the **243 records** (out of 243 requested) whose
`idweb` appears in the manual validation sample.

## What was extracted

| Item | Count |
|---|---|
| Unique idwebs requested (source + candidate + nearest-later) | 243 |
| Records found in JSON export | 243 |
| Missing IDs (not found in local export) | 0 |
| Raw JSON source used | `/home/senghakrou/stage-1/data/raw/boamp_full` |
| Files scanned | 348 |

Missing IDs are documented in:
`event_validation/outputs/boamp_150_sample_missing_ids_from_raw_json.csv`

They may be absent because:
- The record was published outside the fetched year range or CPV pre-filter.
- The notice was removed or superseded on the BOAMP platform.
- The `idweb` was assigned by the matching algorithm from a different data vintage.

## How to re-run

```bash
cd /path/to/stage-1
python event_validation/extract_boamp_validation_records_from_json.py
# Or specify a different directory:
python event_validation/extract_boamp_validation_records_from_json.py --raw-json-dir data/raw/boamp_sample
```

## Output files

- `event_validation/outputs/boamp_150_sample_records_from_raw_json.csv` — one row per extracted record
- `event_validation/outputs/boamp_150_sample_missing_ids_from_raw_json.csv` — unmatched IDs
- `event_validation/outputs/boamp_event_validation_audit.xlsx` — sheet `BOAMP_Raw_Records` appended
