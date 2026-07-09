from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CURRENT = ROOT / "data" / "raw" / "boamp_current"
PROCESSED_CURRENT = ROOT / "data" / "processed" / "boamp_current"
SYNTHETIC_CURRENT = ROOT / "data" / "synthetic" / "boamp_synthetic_benchmark_current"
TABLES_DATA = ROOT / "reports" / "tables" / "data"
TABLES_LINKAGE = ROOT / "reports" / "tables" / "linkage"
TABLES_VALIDATION = ROOT / "reports" / "tables" / "validation"
TABLES_SURVIVAL = ROOT / "reports" / "tables" / "survival"
TABLES_AUDIT = ROOT / "reports" / "tables" / "audit"
FIGURES_DATA = ROOT / "reports" / "figures" / "data"
FIGURES_LINKAGE = ROOT / "reports" / "figures" / "linkage"
FIGURES_SURVIVAL = ROOT / "reports" / "figures" / "survival"
RUN_LOG_DIR = ROOT / "reports" / "run_logs"

PROXY_EVENT_NOTE = (
    "proxy recurrence: identifiable reappearance of a similar procurement need; "
    "not a legally verified renewal chain"
)

CURRENT_DIRS = [
    RAW_CURRENT,
    PROCESSED_CURRENT,
    SYNTHETIC_CURRENT,
    TABLES_DATA,
    TABLES_LINKAGE,
    TABLES_VALIDATION,
    TABLES_SURVIVAL,
    TABLES_AUDIT,
    FIGURES_DATA,
    FIGURES_LINKAGE,
    FIGURES_SURVIVAL,
    RUN_LOG_DIR,
]


def ensure_dirs() -> None:
    for path in CURRENT_DIRS:
        path.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def append_run_log(lines: list[str]) -> None:
    path = RUN_LOG_DIR / "enriched_dataset_run_log.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_buyer_name(value) -> str:
    text = normalize_text(value)
    text = re.sub(r"\b(de|la|le|les|du|des|d|l|et|en|au|aux|sur|par|pour|a)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_digits(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    text = re.sub(r"\.0$", "", text)
    digits = re.sub(r"\D", "", text)
    return digits or None


def clean_siret(value) -> str | None:
    digits = clean_digits(value)
    if digits and len(digits) == 14:
        return digits
    return None


def clean_siren(value) -> str | None:
    digits = clean_digits(value)
    if digits and len(digits) == 9:
        return digits
    if digits and len(digits) == 14:
        return digits[:9]
    return None


def clean_cpv(value) -> str | None:
    digits = clean_digits(value)
    if not digits:
        return None
    return digits[:8].zfill(8)


def is_generic_cpv(value) -> bool:
    cpv = clean_cpv(value)
    return bool(cpv and cpv.endswith("000000"))


def cpv_score(src, cand) -> float:
    a = clean_cpv(src)
    b = clean_cpv(cand)
    if a is None or b is None:
        return np.nan
    same_div = a[:2] == b[:2]
    if is_generic_cpv(a) or is_generic_cpv(b):
        return 0.20 if same_div else 0.0
    if a[:8] == b[:8]:
        return 1.0
    if a[:5] == b[:5]:
        return 0.8
    if a[:4] == b[:4]:
        return 0.6
    if a[:3] == b[:3]:
        return 0.4
    return 0.2 if same_div else 0.0


def duration_clean(value, default: float = 48.0, lo: float = 1.0, hi: float = 120.0) -> tuple[float, bool]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default, True
    if math.isnan(v) or v < lo or v > hi:
        return default, True
    return float(v), False


def month_diff(start, end) -> float:
    return (pd.Timestamp(end) - pd.Timestamp(start)).days / 30.44


def temporal_score(gap_months, expected_months, window: float = 6.0) -> float:
    if pd.isna(gap_months) or pd.isna(expected_months):
        return np.nan
    return float(np.clip(1.0 - abs(float(gap_months) - float(expected_months)) / window, 0.0, 1.0))


def text_tokens(text) -> set[str]:
    return {t for t in normalize_text(text).split() if len(t) >= 3}


def jaccard_from_sets(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def current_study_end(metadata: dict | None = None) -> pd.Timestamp:
    metadata = metadata or read_json(RAW_CURRENT / "download_metadata.json", {})
    value = (
        metadata.get("actual_date_range", {}).get("max_date")
        or metadata.get("requested_date_range", {}).get("end_date")
    )
    if not value:
        raise ValueError("Cannot derive current study end date; run downloader first.")
    return pd.Timestamp(value).normalize()


def buyer_key_from_parts(
    siret_clean: str | None,
    siren_clean: str | None,
    siren_from_siret: str | None,
    siren_enriched: str | None,
    buyer_name_normalized: str,
) -> tuple[str, str, str]:
    if siret_clean:
        return f"SIRET:{siret_clean}", "SIRET", "valid_siret"
    if siren_clean:
        return f"SIREN:{siren_clean}", "SIREN", "valid_siren"
    if siren_from_siret:
        return f"SIREN:{siren_from_siret}", "SIREN_FROM_SIRET", "siren_from_siret"
    if siren_enriched:
        return f"SIREN:{siren_enriched}", "SIREN_ENRICHED", "external_enrichment"
    return f"NAME:{buyer_name_normalized}", "NAME", "normalized_buyer_name"


def save_dual_figure(fig, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=300, bbox_inches="tight")


def source_trace_rows(section: str, metrics: dict[str, object], source_file: Path, note: str = "") -> list[dict]:
    return [
        {
            "section": section,
            "metric": key,
            "value": value,
            "source_file": str(source_file.relative_to(ROOT)) if source_file.is_absolute() else str(source_file),
            "source_column_or_table": key,
            "note": note,
        }
        for key, value in metrics.items()
    ]
