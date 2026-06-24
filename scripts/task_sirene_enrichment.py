"""
DEPRECATED (2026-06-24): This script is superseded by the structured pipeline
in buyer_siren_enrichment/ (step1_build_unique_buyers.py through step7_compare.py).
Its output boamp_full_clean_sirene.csv is a legacy file; use
data/processed/boamp_full_clean_siren_enriched.csv instead.

---

SIRENE enrichment for BOAMP buyers (nomacheteur) and titulaires.

Matching pipeline per entity:
  1. Detect entity type from name patterns (commune, SDIS, CHU, région, …)
  2. Build a short targeted API query + optional nature_juridique filter
  3. For buyers: add département filter to narrow geographic scope
  4. Score each API candidate: token_sort_ratio on normalized names
  5. Accept best candidate when score >= threshold
  6. Cache all lookups to avoid redundant API calls

Output columns added:
  buyer_siren        buyer_siret_sirene   buyer_name_sirene
  buyer_match_score  buyer_match_conf
  titulaire_siren    titulaire_siret_sirene  titulaire_name_sirene
  titulaire_match_score  titulaire_match_conf
"""

import re
import time
import unicodedata
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests
from rapidfuzz import fuzz

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
INPUT      = ROOT / "data/processed/boamp_full_clean.csv"
OUTPUT     = ROOT / "data/processed/boamp_full_clean_sirene.csv"
CACHE_FILE = ROOT / "data/processed/_sirene_cache.json"

# ── API ────────────────────────────────────────────────────────────────────────
API_URL    = "https://recherche-entreprises.api.gouv.fr/search"
CALL_DELAY = 0.15   # ~6 req/s — polite
TIMEOUT    = 12

# ── thresholds ─────────────────────────────────────────────────────────────────
HIGH_THRESHOLD   = 85
MEDIUM_THRESHOLD = 70
LOW_THRESHOLD    = 55

# ── nature_juridique codes for French public entities ──────────────────────────
NJ_COMMUNE     = "7210"   # Commune
NJ_DEPT        = "7220"   # Département
NJ_REGION      = "7230"   # Région
NJ_CCAS        = "7361"   # Centre communal d'action sociale
NJ_HOSP        = "7362"   # Centre hospitalier, hôpital
NJ_CHU         = "7364"   # Centre hospitalier universitaire
NJ_EPCI        = "7340"   # Etablissement public de coopération intercommunale
NJ_SDIS        = "7372"   # Service départemental d'incendie et de secours
NJ_UNIV        = "7383"   # Université
NJ_TRIBUNAL    = "7117"   # Tribunal administratif
NJ_CHAMBRE     = "7120"   # Chambre de commerce / chambre des métiers (approx)
NJ_OPAC        = "4120"   # OPH / OPAC (office public de l'habitat)


# ── entity-type detection rules ────────────────────────────────────────────────
# Each rule: (regex pattern, nature_juridique, query_builder_key)
# query_builder_key drives _build_query()
_ENTITY_RULES = [
    (re.compile(r"\bSDIS\b",                    re.I), NJ_SDIS,     "SDIS"),
    (re.compile(r"\bVille\s+de\b",              re.I), NJ_COMMUNE,  "COMMUNE"),
    (re.compile(r"\bCommune\s+de\b",            re.I), NJ_COMMUNE,  "COMMUNE"),
    (re.compile(r"\bMairie\s+de\b",             re.I), NJ_COMMUNE,  "COMMUNE"),
    (re.compile(r"\bConseil\s+Général\b",       re.I), NJ_DEPT,     "DEPT"),
    (re.compile(r"\bConseil\s+Départemental\b", re.I), NJ_DEPT,     "DEPT"),
    (re.compile(r"\bDépartement\b",             re.I), NJ_DEPT,     "DEPT"),
    (re.compile(r"\bConseil\s+Régional\b",      re.I), NJ_REGION,   "REGION"),
    (re.compile(r"\bRégion\b",                  re.I), NJ_REGION,   "REGION"),
    (re.compile(r"\bCHU\b",                     re.I), NJ_CHU,      "CHU"),
    (re.compile(r"\bCHR\b",                     re.I), NJ_CHU,      "CHU"),
    (re.compile(r"\bCH\s+de\b|\bCentre\s+Hosp", re.I), NJ_HOSP,   "HOSP"),
    (re.compile(r"\bCCAS\b",                    re.I), NJ_CCAS,     "CCAS"),
    (re.compile(r"\bCommunauté\b",              re.I), NJ_EPCI,     "EPCI"),
    (re.compile(r"\bSMICTOM\b|\bSivom\b|\bSyndicat\s+Mixte\b", re.I), NJ_EPCI, "EPCI"),
    (re.compile(r"\bUniversité\b",              re.I), NJ_UNIV,     "UNIV"),
    (re.compile(r"\bTribunal\s+Administratif\b",re.I), NJ_TRIBUNAL, "TRIBUNAL"),
    (re.compile(r"\bOPAC\b|\bOPH\b|\bOffice\s+Public\s+de\s+l.Habitat\b", re.I), NJ_OPAC, "OPAC"),
]


@dataclass
class EntitySpec:
    nature_juridique: Optional[str]
    query_key: str          # e.g. "COMMUNE", "SDIS", "DEFAULT"
    city_hint: str          # extracted city/region name for query building


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _norm(s: str) -> str:
    """Full normalization: accents + lowercase + punctuation → spaces, multi-spaces stripped."""
    s = _strip_accents(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s{2,}", " ", s).strip()


# legal suffixes to strip when comparing names
_LEGAL_RE = re.compile(
    r"\b(s\.?a\.?s?\.?|s\.?a\.?r\.?l\.?|e\.?u\.?r\.?l\.?|s\.?n\.?c\.?|"
    r"s\.?c\.?p\.?|s\.?e\.?l\.?a\.?s?\.?|g\.?i\.?e\.?|s\.?e\.?m\.?|s\.?p\.?l\.?|"
    r"societe|groupe|compagnie|cie|etablissements?|ets|associ[ae]tion|fondation|syndicat)\b",
    re.I
)
_STOP_RE = re.compile(r"\b(de|la|le|les|du|des|d|l|et|en|au|aux|sur|par|pour|a)\b", re.I)
_MULTI  = re.compile(r"\s{2,}")


def normalize_for_score(s: str) -> str:
    """Normalize name for similarity scoring (removes stopwords + legal suffixes)."""
    s = _norm(s)
    s = _LEGAL_RE.sub(" ", s)
    s = _STOP_RE.sub(" ", s)
    return _MULTI.sub(" ", s).strip()


def _extract_after_keyword(raw: str, keywords: list[str]) -> str:
    """Extract the part of the name after a keyword like 'Ville de', 'SDIS de', etc."""
    for kw in keywords:
        m = re.search(kw + r"\s+(?:de\s+|d['']\s*)?(.+)", raw, re.I)
        if m:
            return m.group(1).strip()
    return raw


def detect_entity(raw_name: str) -> EntitySpec:
    """
    Detect the public entity type and extract a city/region hint.
    Returns EntitySpec(nature_juridique, query_key, city_hint).
    """
    for pattern, nj, key in _ENTITY_RULES:
        if pattern.search(raw_name):
            # extract city hint: text after the matched keyword
            hint = raw_name
            if key == "COMMUNE":
                hint = _extract_after_keyword(raw_name, [r"Ville\s+de", r"Commune\s+de", r"Mairie\s+de"])
            elif key == "SDIS":
                hint = _extract_after_keyword(raw_name, [r"SDIS\s+de", r"SDIS"])
            elif key in ("DEPT",):
                hint = _extract_after_keyword(raw_name, [r"Conseil\s+Général\s+de", r"Conseil\s+Départemental\s+de", r"Département\s+de"])
            elif key == "REGION":
                hint = _extract_after_keyword(raw_name, [r"Conseil\s+Régional\s+de", r"Région\s+de", r"Région"])
            elif key == "CHU":
                hint = _extract_after_keyword(raw_name, [r"CHU\s+de", r"CHR\s+de"])
            elif key == "HOSP":
                hint = _extract_after_keyword(raw_name, [r"CH\s+de", r"Centre\s+Hospitalier\s+de"])
            elif key == "CCAS":
                hint = _extract_after_keyword(raw_name, [r"CCAS\s+de"])
            elif key in ("EPCI", "TRIBUNAL", "UNIV", "OPAC"):
                hint = raw_name
            return EntitySpec(nj, key, hint)

    return EntitySpec(None, "DEFAULT", raw_name)


def build_query(raw_name: str, spec: EntitySpec) -> str:
    """Build the short API query string from entity spec."""
    hint_norm = _norm(spec.city_hint)

    if spec.query_key == "COMMUNE":
        return f"commune {hint_norm}"

    if spec.query_key == "SDIS":
        # SIRENE stores SDIS as "SCE DEPARTEMENTAL INCENDIE ET SECOURS (SDIS)" with no city name.
        # Keep query short; dept filter alone disambiguates between departments.
        return "incendie secours"

    if spec.query_key == "DEPT":
        return f"departement {hint_norm}"

    if spec.query_key == "REGION":
        return f"region {hint_norm}"

    if spec.query_key == "CHU":
        return f"chu {hint_norm}"

    if spec.query_key == "HOSP":
        return f"centre hospitalier {hint_norm}"

    if spec.query_key == "CCAS":
        return f"ccas {hint_norm}"

    if spec.query_key == "EPCI":
        return normalize_for_score(raw_name)

    # DEFAULT: normalize the raw name
    return normalize_for_score(raw_name)


# ── SIRENE API ─────────────────────────────────────────────────────────────────

_CACHE: dict[str, dict] = {}


def _load_cache() -> None:
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            _CACHE.update(json.load(f))


def _save_cache() -> None:
    with open(CACHE_FILE, "w") as f:
        json.dump(_CACHE, f, ensure_ascii=False, indent=2)


def _api_call(q: str, departement: str | None, nature_juridique: str | None) -> list[dict]:
    params: dict = {"q": q, "limite": 10, "etat_administratif": "A"}
    if departement:
        dep = str(departement).split("|")[0].strip().zfill(2)
        if dep not in ("00", ""):
            params["departement"] = dep
    if nature_juridique:
        params["nature_juridique"] = nature_juridique
    try:
        r = requests.get(API_URL, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []


def _score(query_norm_for_score: str, candidate: dict) -> float:
    cand_name = normalize_for_score(candidate.get("nom_complet") or "")
    if not cand_name:
        return 0.0
    base = fuzz.token_sort_ratio(query_norm_for_score, cand_name)
    # bonus: fraction of query tokens present in candidate
    q_tok = set(query_norm_for_score.split())
    c_tok = set(cand_name.split())
    if q_tok:
        overlap = len(q_tok & c_tok) / len(q_tok)
        base += overlap * 8
    return min(base, 100.0)


def lookup(raw_name: str, departement: str | None = None) -> dict:
    """
    Look up one entity name in SIRENE.
    Returns dict: siren, siret, sirene_name, score, confidence, query_used
    """
    cache_key = f"{_norm(raw_name)}||{departement or ''}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    spec      = detect_entity(raw_name)
    api_query = build_query(raw_name, spec)

    # Build score_ref: what we compare SIRENE candidate names against.
    # SDIS: SIRENE uses "SCE DEPARTEMENTAL INCENDIE ET SECOURS (SDIS)", not the short form.
    # COMMUNE: SIRENE stores "COMMUNE DE X" never "VILLE DE X", so rewrite score_ref.
    if spec.query_key == "SDIS":
        score_ref = "sce departemental incendie secours sdis"
    elif spec.query_key == "COMMUNE":
        # replace "ville" / "mairie" with "commune" so the comparison aligns with SIRENE naming
        city_norm = normalize_for_score(spec.city_hint)
        score_ref = f"commune {city_norm}"
    else:
        score_ref = normalize_for_score(raw_name)

    def _best_from(candidates: list[dict]) -> tuple[float, dict | None]:
        if not candidates:
            return 0.0, None
        # use index as tiebreaker so dicts are never compared directly
        scored = sorted(
            [(- _score(score_ref, c), i, c) for i, c in enumerate(candidates)]
        )
        neg_score, _, best_cand = scored[0]
        return -neg_score, best_cand

    # For SDIS, nature_juridique=7372 returns 0 results (API limitation); skip it
    # and rely on the département filter which already uniquely identifies one SDIS.
    pass1_nj = None if spec.query_key == "SDIS" else spec.nature_juridique

    # ── pass 1: full filters (nj + dept) ──────────────────────────────────────
    cands = _api_call(api_query, departement, pass1_nj)
    time.sleep(CALL_DELAY)
    best_score, best = _best_from(cands)

    # If both nj AND dept filters were applied and only 1 result came back,
    # that's a strongly constrained match (e.g. one CHU per department).
    # Promote it to at least MEDIUM confidence.
    if (pass1_nj and departement and len(cands) == 1
            and best is not None and best_score < MEDIUM_THRESHOLD):
        best_score = MEDIUM_THRESHOLD

    # ── pass 2: drop nj filter if no good hit ─────────────────────────────────
    if best_score < MEDIUM_THRESHOLD and spec.nature_juridique:
        cands2 = _api_call(api_query, departement, None)
        time.sleep(CALL_DELAY)
        s2, c2 = _best_from(cands2)
        if s2 > best_score:
            best_score, best = s2, c2

    # ── pass 3: drop dept filter too ──────────────────────────────────────────
    if best_score < MEDIUM_THRESHOLD and departement:
        cands3 = _api_call(api_query, None, spec.nature_juridique)
        time.sleep(CALL_DELAY)
        s3, c3 = _best_from(cands3)
        if s3 > best_score:
            best_score, best = s3, c3

    # ── pass 4: raw name as query, no filters ─────────────────────────────────
    raw_q = normalize_for_score(raw_name)
    if best_score < LOW_THRESHOLD and raw_q != api_query:
        cands4 = _api_call(raw_q, departement, None)
        time.sleep(CALL_DELAY)
        s4, c4 = _best_from(cands4)
        if s4 > best_score:
            best_score, best = s4, c4

    if best is None or best_score < LOW_THRESHOLD:
        result = dict(siren=None, siret=None, sirene_name=None,
                      score=0.0, confidence="SKIP", query_used=api_query)
    else:
        if best_score >= HIGH_THRESHOLD:
            confidence = "HIGH"
        elif best_score >= MEDIUM_THRESHOLD:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        result = dict(
            siren=best.get("siren"),
            siret=best.get("siege", {}).get("siret"),
            sirene_name=best.get("nom_complet"),
            score=round(best_score, 1),
            confidence=confidence,
            query_used=api_query,
        )

    _CACHE[cache_key] = result
    return result


# ── enrichment functions ───────────────────────────────────────────────────────

def enrich_buyers(df: pd.DataFrame) -> pd.DataFrame:
    print("\n── Enriching buyers ──────────────────────────────────")
    pairs = (
        df[["nomacheteur", "code_departement"]]
        .drop_duplicates("nomacheteur")
        .dropna(subset=["nomacheteur"])
    )
    print(f"  {len(pairs)} unique buyer names")

    results: dict[str, dict] = {}
    for i, row in enumerate(pairs.itertuples(), 1):
        name = row.nomacheteur
        dep  = str(row.code_departement) if pd.notna(row.code_departement) else None
        results[name] = lookup(name, departement=dep)
        if i % 50 == 0 or i == len(pairs):
            print(f"  {i}/{len(pairs)} done")
            _save_cache()

    df["buyer_siren"]        = df["nomacheteur"].map(lambda n: results.get(n, {}).get("siren"))
    df["buyer_siret_sirene"] = df["nomacheteur"].map(lambda n: results.get(n, {}).get("siret"))
    df["buyer_name_sirene"]  = df["nomacheteur"].map(lambda n: results.get(n, {}).get("sirene_name"))
    df["buyer_match_score"]  = df["nomacheteur"].map(lambda n: results.get(n, {}).get("score"))
    df["buyer_match_conf"]   = df["nomacheteur"].map(lambda n: results.get(n, {}).get("confidence"))

    print("  Buyer confidence distribution:")
    print(df["buyer_match_conf"].value_counts(dropna=False).to_string())
    return df


def enrich_titulaires(df: pd.DataFrame) -> pd.DataFrame:
    print("\n── Enriching titulaires ──────────────────────────────")

    def primary_tit(val):
        if pd.isna(val):
            return None
        return str(val).split("|")[0].strip()

    df["titulaire_primary"] = df["titulaire"].apply(primary_tit)
    unique_tits = df["titulaire_primary"].dropna().unique()
    print(f"  {len(unique_tits)} unique primary titulaire names")

    results: dict[str, dict] = {}
    for i, name in enumerate(unique_tits, 1):
        results[name] = lookup(name, departement=None)
        if i % 50 == 0 or i == len(unique_tits):
            print(f"  {i}/{len(unique_tits)} done")
            _save_cache()

    df["titulaire_siren"]        = df["titulaire_primary"].map(lambda n: results.get(n, {}).get("siren") if n else None)
    df["titulaire_siret_sirene"] = df["titulaire_primary"].map(lambda n: results.get(n, {}).get("siret") if n else None)
    df["titulaire_name_sirene"]  = df["titulaire_primary"].map(lambda n: results.get(n, {}).get("sirene_name") if n else None)
    df["titulaire_match_score"]  = df["titulaire_primary"].map(lambda n: results.get(n, {}).get("score") if n else None)
    df["titulaire_match_conf"]   = df["titulaire_primary"].map(lambda n: results.get(n, {}).get("confidence") if n else None)

    print("  Titulaire confidence distribution:")
    print(df["titulaire_match_conf"].value_counts(dropna=False).to_string())
    return df


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    _load_cache()
    print(f"Cache loaded: {len(_CACHE)} entries")

    df = pd.read_csv(INPUT)
    print(f"BOAMP rows loaded: {len(df)}")

    df = enrich_buyers(df)
    df = enrich_titulaires(df)

    _save_cache()
    df.to_csv(OUTPUT, index=False)
    print(f"\nSaved → {OUTPUT}")

    # ── summary report ────────────────────────────────────────────────────────
    total = len(df)
    print("\n═══ ENRICHMENT SUMMARY ═══")
    for entity, conf_col, siret_col in [
        ("BUYER",     "buyer_match_conf",     "buyer_siret_sirene"),
        ("TITULAIRE", "titulaire_match_conf",  "titulaire_siret_sirene"),
    ]:
        high   = (df[conf_col] == "HIGH").sum()
        medium = (df[conf_col] == "MEDIUM").sum()
        low    = (df[conf_col] == "LOW").sum()
        skip   = (df[conf_col] == "SKIP").sum()
        null   = df[conf_col].isna().sum()
        siret_filled = df[siret_col].notna().sum()
        print(f"\n{entity} (total rows = {total}):")
        print(f"  HIGH   : {high:5d}  ({high/total*100:5.1f}%)")
        print(f"  MEDIUM : {medium:5d}  ({medium/total*100:5.1f}%)")
        print(f"  LOW    : {low:5d}  ({low/total*100:5.1f}%)")
        print(f"  SKIP   : {skip:5d}  ({skip/total*100:5.1f}%)")
        print(f"  null   : {null:5d}  (no titulaire / no match attempted)")
        print(f"  SIRET filled: {siret_filled} rows  ({siret_filled/total*100:.1f}%)")


if __name__ == "__main__":
    main()
