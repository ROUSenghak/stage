"""Step 2 — Query API Recherche d'Entreprises and build the candidates table.

For every unique BOAMP buyer (from step1 output):
  - check local cache first
  - call the API if uncached (≤5 req/s)
  - capture ALL returned candidates (up to 10) with per-candidate scores
  - save raw candidates table and update cache

Reuses API helpers from scripts/task_sirene_enrichment.py without re-implementing
them (imported via sys.path).

Outputs
-------
  buyer_siren_enrichment/cache/sirene_cache.json    (seeded from existing cache)
  buyer_siren_enrichment/outputs/boamp_buyer_siren_candidates.csv
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

# Import helpers from the existing enrichment script
from task_sirene_enrichment import (
    _norm,
    normalize_for_score,
    detect_entity,
    build_query,
    _api_call,
    _score,
    CALL_DELAY,
)

# ── paths ──────────────────────────────────────────────────────────────────────
ENRICH_DIR   = ROOT / "buyer_siren_enrichment"
BUYERS_CSV   = ENRICH_DIR / "outputs" / "boamp_unique_buyers_for_enrichment.csv"
OUT_CANDS    = ENRICH_DIR / "outputs" / "boamp_buyer_siren_candidates.csv"
CACHE_FILE   = ENRICH_DIR / "cache" / "sirene_cache.json"
OLD_CACHE    = ROOT / "data" / "processed" / "_sirene_cache.json"
LOG_FILE     = ENRICH_DIR / "logs" / "api_failures.log"

# ── logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)


# ── cache helpers ──────────────────────────────────────────────────────────────
_CACHE: dict[str, list[dict]] = {}


def _load_cache() -> None:
    """Load cache; seed from the old cache if new one does not exist yet."""
    if not CACHE_FILE.exists() and OLD_CACHE.exists():
        shutil.copy(OLD_CACHE, CACHE_FILE)
        print(f"  Seeded cache from {OLD_CACHE}")
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            _CACHE.update(json.load(f))
        print(f"  Cache loaded: {len(_CACHE):,} entries")


def _save_cache() -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_CACHE, f, ensure_ascii=False, indent=2)


def _cache_key(name: str, dept: str | None) -> str:
    return f"{_norm(name)}||{dept or ''}"


# ── candidate extraction ───────────────────────────────────────────────────────

def _candidates_for_buyer(raw_name: str, dept_code: str | None) -> list[dict]:
    """
    Return all API candidates for one buyer as a list of dicts.
    Uses a 3-pass strategy (with dept+nj, without nj, without dept).
    Results cached per (normalized_name, dept).
    """
    key = _cache_key(raw_name, dept_code)

    if key in _CACHE and isinstance(_CACHE[key], list):
        return _CACHE[key]

    # If the cache holds the old format (a single result dict), re-query.
    spec       = detect_entity(raw_name)
    api_query  = build_query(raw_name, spec)

    pass1_nj = None if spec.query_key == "SDIS" else spec.nature_juridique

    # pass 1: dept + nj
    cands = _api_call(api_query, dept_code, pass1_nj)
    time.sleep(CALL_DELAY)

    # pass 2: no nj filter if nothing good yet
    if not cands and spec.nature_juridique:
        cands = _api_call(api_query, dept_code, None)
        time.sleep(CALL_DELAY)

    # pass 3: no dept filter
    if not cands and dept_code:
        cands = _api_call(api_query, None, spec.nature_juridique)
        time.sleep(CALL_DELAY)

    # pass 4: raw normalized name, no filters
    raw_q = normalize_for_score(raw_name)
    if not cands and raw_q != api_query:
        cands = _api_call(raw_q, dept_code, None)
        time.sleep(CALL_DELAY)

    _CACHE[key] = cands  # cache the raw list
    return cands


def _score_ref(raw_name: str, spec) -> str:
    """Same score-reference logic as in task_sirene_enrichment.lookup()."""
    if spec.query_key == "SDIS":
        return "sce departemental incendie secours sdis"
    if spec.query_key == "COMMUNE":
        city_norm = normalize_for_score(spec.city_hint)
        return f"commune {city_norm}"
    return normalize_for_score(raw_name)


def _dept_of_candidate(cand: dict) -> str | None:
    siege = cand.get("siege") or {}
    dept = siege.get("departement") or siege.get("code_departement")
    if dept:
        return str(dept).zfill(2)
    cp = str(siege.get("code_postal") or "")
    return cp[:2] if len(cp) >= 2 else None


# ── main per-buyer enrichment ──────────────────────────────────────────────────

def enrich_buyers(buyers: pd.DataFrame) -> pd.DataFrame:
    """Query API for each buyer, build flat candidates table."""
    rows = []

    total = len(buyers)
    for i, row in enumerate(buyers.itertuples(index=False), 1):
        raw_name   = row.buyer_name_raw
        dept_code  = row.dept_code if not pd.isna(row.dept_code) else None
        buyer_key  = row.buyer_key
        name_clean = row.buyer_name_clean

        spec       = detect_entity(raw_name)
        api_query  = build_query(raw_name, spec)
        score_ref_ = _score_ref(raw_name, spec)

        try:
            cands = _candidates_for_buyer(raw_name, dept_code)
        except Exception as exc:
            logging.warning("API error for %r: %s", raw_name, exc)
            cands = []

        if not cands:
            rows.append({
                "buyer_name_raw":        raw_name,
                "buyer_name_clean":      name_clean,
                "buyer_key":             buyer_key,
                "dept_code":             dept_code,
                "query_used":            api_query,
                "entity_type_detected":  spec.query_key,
                "nature_juridique_filter": spec.nature_juridique,
                "candidate_rank":        None,
                "candidate_siren":       None,
                "candidate_siret":       None,
                "candidate_name":        None,
                "candidate_naf":         None,
                "candidate_nature_juridique": None,
                "candidate_city":        None,
                "candidate_postal_code": None,
                "name_similarity":       0.0,
                "dept_match":            False,
                "enrichment_score":      0.0,
            })
        else:
            for rank, cand in enumerate(cands, 1):
                siege = cand.get("siege") or {}
                sim   = _score(score_ref_, cand)
                cand_dept = _dept_of_candidate(cand)
                dept_match = (
                    bool(dept_code and cand_dept and
                         cand_dept.lstrip("0") == str(dept_code).lstrip("0"))
                )
                rows.append({
                    "buyer_name_raw":        raw_name,
                    "buyer_name_clean":      name_clean,
                    "buyer_key":             buyer_key,
                    "dept_code":             dept_code,
                    "query_used":            api_query,
                    "entity_type_detected":  spec.query_key,
                    "nature_juridique_filter": spec.nature_juridique,
                    "candidate_rank":        rank,
                    "candidate_siren":       cand.get("siren"),
                    "candidate_siret":       siege.get("siret"),
                    "candidate_name":        cand.get("nom_complet"),
                    "candidate_naf":         cand.get("activite_principale"),
                    "candidate_nature_juridique": cand.get("nature_juridique"),
                    "candidate_city":        siege.get("ville") or siege.get("libelle_commune"),
                    "candidate_postal_code": siege.get("code_postal"),
                    "name_similarity":       round(sim, 1),
                    "dept_match":            dept_match,
                    "enrichment_score":      round(sim, 1),
                })

        if i % 50 == 0 or i == total:
            print(f"  {i}/{total} buyers processed")
            _save_cache()

    return pd.DataFrame(rows)


def main() -> None:
    for d in [ENRICH_DIR / "outputs", ENRICH_DIR / "cache", ENRICH_DIR / "logs"]:
        d.mkdir(parents=True, exist_ok=True)

    _load_cache()

    buyers = pd.read_csv(BUYERS_CSV, dtype={"dept_code": str, "postal_code": str})
    print(f"Buyers to process: {len(buyers):,}")

    print("\n── Querying API Recherche d'Entreprises ──────────────────────────")
    cands = enrich_buyers(buyers)

    _save_cache()
    cands.to_csv(OUT_CANDS, index=False)

    n_buyers    = buyers["buyer_name_raw"].nunique()
    n_with_cand = cands[cands["candidate_rank"].notna()]["buyer_name_raw"].nunique()
    print(f"\nCandidates table: {len(cands):,} rows for {n_buyers:,} buyers")
    print(f"Buyers with ≥1 candidate: {n_with_cand:,} ({n_with_cand/n_buyers*100:.1f}%)")
    print(f"Saved → {OUT_CANDS}")
    print(f"Cache: {len(_CACHE):,} entries → {CACHE_FILE}")


if __name__ == "__main__":
    main()
