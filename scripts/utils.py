"""Shared utilities for Week 1 data exploration (BOAMP / DECP).

This module contains:
  - BOAMP Explore-API access helpers (with retry/backoff),
  - parsers for the nested `donnees` JSON blob of BOAMP notices,
  - a generic DataFrame profiling function reused for both sources,
  - a small Markdown table writer (avoids the `tabulate` dependency).

No modeling here: Week 1 is strictly exploration and documentation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

# --------------------------------------------------------------------------
# Constants — scope of the internship corpus (see Internship Guide §3.2.2)
# --------------------------------------------------------------------------

# BOAMP open-data mirror (api.boamp.fr redirects to this Opendatasoft portal)
BOAMP_API = (
    "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/"
    "catalog/datasets/boamp/records"
)

# Pays de la Loire department codes
PDL_DEPARTMENTS = ["44", "49", "53", "72", "85"]

# CPV divisions that define "digital" contracts for this internship
DIGITAL_CPV_PREFIXES = ("48", "72", "32", "35")

# Study period
PERIOD_START = "2015-01-01"
PERIOD_END = "2024-12-31"

# Project-relative output directories
ROOT = Path(__file__).resolve().parent.parent
RAW_BOAMP_DIR = ROOT / "data" / "raw" / "boamp_sample"
RAW_DECP_DIR = ROOT / "data" / "raw" / "decp"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"


# --------------------------------------------------------------------------
# BOAMP API access
# --------------------------------------------------------------------------

def boamp_get(params: dict, max_retries: int = 4, timeout: int = 30) -> dict:
    """GET one page from the BOAMP Explore API with retry + exponential backoff.

    Raises RuntimeError after `max_retries` failures so callers can log the
    error and fall back to the annual Open Data files (documented fallback).
    """
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(BOAMP_API, params=params, timeout=timeout)
            if resp.status_code == 429:  # rate-limited: wait longer and retry
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as err:  # network error, JSON error, HTTP error
            last_err = err
            time.sleep(2 ** attempt)
    raise RuntimeError(f"BOAMP API failed after {max_retries} retries: {last_err}")


def pdl_where_clause(year: int) -> str:
    """ODSQL filter: Pays de la Loire departments + one calendar year +
    server-side pre-filter on digital CPV divisions inside `donnees`.

    CPV lives inside the JSON-encoded `donnees` string, in TWO formats:
      - legacy BOAMP forms (until ~2023):  "CPV": {"PRINCIPAL": "48..."}
      - EU eForms/UBL (from 2024):         "cbc:ItemClassificationCode":
                                           {"@listName": "cpv", "#text": "48..."}
    Both serializations are targeted by the LIKE clauses below. These are only
    a *pre-filter*: every kept record is re-checked client-side after parsing
    `donnees` (see extract_cpv_codes).
    """
    deps = ",".join(f'"{d}"' for d in PDL_DEPARTMENTS)
    likes = []
    for p in DIGITAL_CPV_PREFIXES:
        likes.append(f'donnees LIKE "\\"PRINCIPAL\\": \\"{p}*"')   # legacy
        likes.append(f'donnees LIKE "cpv\\", \\"#text\\": \\"{p}*"')  # eForms
    return (
        f"code_departement IN ({deps}) "
        f"AND dateparution >= date'{year}-01-01' "
        f"AND dateparution <= date'{year}-12-31' "
        f"AND ({' OR '.join(likes)})"
    )


# --------------------------------------------------------------------------
# Parsing the nested `donnees` blob
# --------------------------------------------------------------------------

def parse_donnees(record: dict) -> dict:
    """Decode the `donnees` field (a JSON string) of a BOAMP record."""
    raw = record.get("donnees")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return {}


def deep_get(d: dict, path: str):
    """Safe nested access: deep_get(d, 'OBJET.CPV.PRINCIPAL')."""
    cur = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def find_values_by_key(obj, wanted: str, _acc=None) -> list:
    """Recursively collect every value whose key equals `wanted`.

    BOAMP notice forms changed over the years, so fields like DUREE_MOIS or
    SIRET can appear at different depths; a recursive search is the robust way
    to profile them.
    """
    if _acc is None:
        _acc = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == wanted:
                _acc.append(v)
            find_values_by_key(v, wanted, _acc)
    elif isinstance(obj, list):
        for item in obj:
            find_values_by_key(item, wanted, _acc)
    return _acc


def _scalar(value):
    """Reduce Opendatasoft XML-derived values ({'@DEVISE':..., '#text':...})
    and lists down to a single scalar (first non-empty)."""
    if isinstance(value, dict):
        return _scalar(value.get("#text"))
    if isinstance(value, list):
        for item in value:
            s = _scalar(item)
            if s not in (None, ""):
                return s
        return None
    return value


def is_eforms(donnees: dict) -> bool:
    """True for the EU eForms/UBL format used by BOAMP from 2024 onwards."""
    return "EFORMS" in donnees


def extract_cpv_codes(donnees: dict) -> list[str]:
    """All CPV codes of a notice (main + per-lot), both BOAMP formats."""
    codes = []
    # legacy format: "CPV": {"PRINCIPAL": ..., "SUPPLEMENTAIRE": ...}
    for cpv in find_values_by_key(donnees, "CPV"):
        if isinstance(cpv, dict):
            for key in ("PRINCIPAL", "SUPPLEMENTAIRE"):
                val = _scalar(cpv.get(key))
                if val:
                    codes.append(str(val))
        elif cpv:
            codes.append(str(_scalar(cpv)))
    # eForms format: "cbc:ItemClassificationCode": {"@listName": "cpv", "#text": ...}
    for icc in find_values_by_key(donnees, "cbc:ItemClassificationCode"):
        items = icc if isinstance(icc, list) else [icc]
        for item in items:
            if isinstance(item, dict) and item.get("@listName") == "cpv":
                val = _scalar(item)
                if val:
                    codes.append(str(val))
    # dedupe, keep order
    return list(dict.fromkeys(codes))


def is_digital(cpv_codes: list[str]) -> bool:
    """True if any CPV code belongs to the digital divisions (48/72/32/35)."""
    return any(c.startswith(DIGITAL_CPV_PREFIXES) for c in cpv_codes)


def extract_duration_months(donnees: dict) -> tuple[float | None, str | None]:
    """Declared contract duration, normalized to months.

    Returns (months, source_field). Legacy BOAMP forms encode duration as
    DUREE_MOIS or DUREE_JOUR (location varies by form version); we exclude the
    offer-validity delay (CONDITION_DELAI.VALIDITE_OFFRE) which is not a
    contract duration. eForms notices use cbc:DurationMeasure (@unitCode) or a
    cac:PlannedPeriod start/end date pair.
    """
    # ---- legacy format -----------------------------------------------------
    # Drop the offer-validity block before searching, it also uses DUREE_JOUR.
    scope = {k: v for k, v in donnees.items() if k != "CONDITION_DELAI"}
    for key, factor in (("DUREE_MOIS", 1.0), ("DUREE_JOUR", 1 / 30.44)):
        for val in find_values_by_key(scope, key):
            val = _scalar(val)
            try:
                return float(str(val).replace(",", ".")) * factor, key
            except (TypeError, ValueError):
                continue
    # ---- eForms format -----------------------------------------------------
    unit_to_months = {"MONTH": 1.0, "DAY": 1 / 30.44, "WEEK": 7 / 30.44,
                      "YEAR": 12.0, "ANN": 12.0}
    for dm in find_values_by_key(donnees, "cbc:DurationMeasure"):
        if isinstance(dm, dict):
            factor = unit_to_months.get(str(dm.get("@unitCode", "")).upper())
            try:
                return float(_scalar(dm)) * factor, "cbc:DurationMeasure"
            except (TypeError, ValueError):
                continue
    for period in find_values_by_key(donnees, "cac:PlannedPeriod"):
        if isinstance(period, dict):
            start = _scalar(period.get("cbc:StartDate"))
            end = _scalar(period.get("cbc:EndDate"))
            try:
                delta = (pd.Timestamp(str(end).rstrip("Z"))
                         - pd.Timestamp(str(start).rstrip("Z"))).days
                return round(delta / 30.44, 1), "cac:PlannedPeriod"
            except (TypeError, ValueError):
                continue
    return None, None


def extract_amount_eur(donnees: dict) -> float | None:
    """First parseable amount, both formats.

    Legacy: estimated value (OBJET.CARACTERISTIQUES.VALEUR) or awarded amount
    (ATTRIBUTION ... MONTANT / ESTIMATION_INITIALE).
    eForms: cbc:TotalAmount (notice result), cbc:PayableAmount (settled
    tender), cbc:EstimatedOverallContractAmount.
    """
    candidates = (
        find_values_by_key(donnees.get("OBJET", {}), "VALEUR")
        + find_values_by_key(donnees.get("ATTRIBUTION", {}), "MONTANT")
        + find_values_by_key(donnees.get("ATTRIBUTION", {}), "ESTIMATION_INITIALE")
        + find_values_by_key(donnees, "cbc:TotalAmount")
        + find_values_by_key(donnees, "cbc:PayableAmount")
        + find_values_by_key(donnees, "cbc:EstimatedOverallContractAmount")
    )
    for cand in candidates:
        val = _scalar(cand)
        try:
            return float(str(val).replace(",", ".").replace(" ", ""))
        except (TypeError, ValueError):
            continue
    return None


def extract_buyer_siret(donnees: dict) -> str | None:
    """Buyer SIRET/SIREN identifier.

    Legacy forms almost never carry it (IDENTITE has no SIRET field on most
    form versions). eForms carries it as cbc:CompanyID under
    efac:Organizations; the buyer is normally the first organization listed.
    """
    for val in find_values_by_key(donnees.get("IDENTITE", {}), "SIRET"):
        if _scalar(val):
            return str(_scalar(val))
    for val in find_values_by_key(donnees, "cbc:CompanyID"):
        if _scalar(val):
            return str(_scalar(val))
    return None


def extract_award_date(donnees: dict) -> str | None:
    """Award date, both formats.

    Legacy: ATTRIBUTION...DATE_ATTRIBUTION. eForms: efac:SettledContract
    cbc:IssueDate, with cac:TenderResult/cbc:AwardDate as fallback —
    excluding the placeholder value 2000-01-01 used by eForms when the award
    date is withheld (documented data-quality issue).
    """
    for val in find_values_by_key(donnees.get("ATTRIBUTION", {}),
                                  "DATE_ATTRIBUTION"):
        if _scalar(val):
            return str(_scalar(val))
    for contract in find_values_by_key(donnees, "efac:SettledContract"):
        for val in find_values_by_key({"x": contract}, "cbc:IssueDate"):
            if _scalar(val):
                return str(_scalar(val)).rstrip("Z")
    for val in find_values_by_key(donnees, "cbc:AwardDate"):
        date = str(_scalar(val) or "").rstrip("Z")
        if date and not date.startswith("2000-01-01"):
            return date
    return None


def extract_boamp_features(record: dict) -> dict:
    """Flatten one BOAMP API record: top-level fields + key nested extracts."""
    donnees = parse_donnees(record)
    cpv_codes = extract_cpv_codes(donnees)
    duration, duration_src = extract_duration_months(donnees)

    def joinlist(value):  # CSV-friendly representation of list fields
        return "|".join(map(str, value)) if isinstance(value, list) else value

    return {
        # ---- top-level API fields (kept as-is for completeness profiling)
        "idweb": record.get("idweb"),
        "dateparution": record.get("dateparution"),
        "datefindiffusion": record.get("datefindiffusion"),
        "datelimitereponse": record.get("datelimitereponse"),
        "nomacheteur": record.get("nomacheteur"),
        "code_departement": joinlist(record.get("code_departement")),
        "famille": record.get("famille"),
        "nature": record.get("nature"),
        "nature_libelle": record.get("nature_libelle"),
        "type_procedure": record.get("type_procedure"),
        "type_marche": joinlist(record.get("type_marche")),
        "type_avis": joinlist(record.get("type_avis")),
        "descripteur_libelle": joinlist(record.get("descripteur_libelle")),
        "objet": record.get("objet"),
        "titulaire": joinlist(record.get("titulaire")),
        "annonce_lie": joinlist(record.get("annonce_lie")),
        "contractfolderid": record.get("contractfolderid"),
        "etat": record.get("etat"),
        "url_avis": record.get("url_avis"),
        # ---- extracted from the nested `donnees` blob (both formats)
        "donnees_format": "eforms" if is_eforms(donnees) else "legacy",
        "cpv_principal": _scalar(deep_get(donnees, "OBJET.CPV.PRINCIPAL"))
                         or (cpv_codes[0] if cpv_codes else None),
        "cpv_all": "|".join(cpv_codes),
        "buyer_siret": extract_buyer_siret(donnees),
        "buyer_cp": _scalar(deep_get(donnees, "IDENTITE.CP"))
                    or _scalar((find_values_by_key(donnees, "cbc:PostalZone")
                                or [None])[0]),
        "buyer_ville": _scalar(deep_get(donnees, "IDENTITE.VILLE"))
                       or _scalar((find_values_by_key(donnees, "cbc:CityName")
                                   or [None])[0]),
        "amount_eur": extract_amount_eur(donnees),
        "duration_months": duration,
        "duration_source_field": duration_src,
        "date_attribution": extract_award_date(donnees),
        "date_publication_anterieure": _scalar(
            (find_values_by_key(donnees.get("PUBLICATION_ANTERIEURE", {}),
                                "DATE_PUBLICATION") or [None])[0]
        ),
    }


# --------------------------------------------------------------------------
# Generic profiling (reused for BOAMP and DECP)
# --------------------------------------------------------------------------

def profile_dataframe(df: pd.DataFrame, notes: dict[str, str] | None = None
                      ) -> pd.DataFrame:
    """Field-by-field profiling table: dtype, completeness, cardinality,
    sample values, free-text notes."""
    notes = notes or {}
    rows = []
    for col in df.columns:
        series = df[col]
        non_null = series.notna() & (series.astype(str).str.strip() != "")
        samples = series[non_null].drop_duplicates().head(4).astype(str)
        samples = [s[:60] + ("…" if len(s) > 60 else "") for s in samples]
        rows.append({
            "field": col,
            "dtype": str(series.dtype),
            "non_null": int(non_null.sum()),
            "missing_pct": round(100 * (1 - non_null.mean()), 1),
            "n_unique": int(series[non_null].nunique()),
            "sample_values": " ; ".join(samples),
            "notes": notes.get(col, ""),
        })
    return pd.DataFrame(rows)


def to_markdown_table(df: pd.DataFrame) -> str:
    """Minimal GitHub-Markdown table writer (escapes pipes)."""
    def esc(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(map(esc, df.columns)) + " |"
    sep = "|" + "|".join(["---"] * len(df.columns)) + "|"
    body = ["| " + " | ".join(esc(v) for v in row) + " |"
            for row in df.itertuples(index=False)]
    return "\n".join([header, sep] + body)
