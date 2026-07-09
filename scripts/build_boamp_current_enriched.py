from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import (
    PROCESSED_CURRENT,
    RAW_CURRENT,
    TABLES_DATA,
    append_run_log,
    buyer_key_from_parts,
    clean_cpv,
    clean_siren,
    clean_siret,
    ensure_dirs,
    is_generic_cpv,
    normalize_buyer_name,
    normalize_text,
    utc_now,
)
from task7_week2_cleaning import apply_amount_flags, apply_duration_flags, build_taxonomy_matcher
from task_sirene_enrichment import CALL_DELAY, _api_call, _score, build_query, detect_entity, normalize_for_score
from utils import PROCESSED_DIR

HIGH_SCORE = 85.0
HIGH_SCORE_LOWER = 75.0
HIGH_MARGIN = 10.0


def load_seed_matches() -> pd.DataFrame:
    seed_path = Path("buyer_siren_enrichment/outputs/boamp_buyer_siren_enriched.csv")
    if not seed_path.exists():
        return pd.DataFrame()
    seed = pd.read_csv(seed_path, dtype=str)
    seed["buyer_name_normalized"] = seed["buyer_name_raw"].map(normalize_buyer_name)
    return seed


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_api_result(raw_name: str, dept_code: str | None, cache: dict) -> dict:
    key = f"{normalize_buyer_name(raw_name)}||{dept_code or ''}"
    if key in cache:
        return cache[key]
    spec = detect_entity(raw_name)
    query = build_query(raw_name, spec)
    cands = _api_call(query, dept_code, None if spec.query_key == "SDIS" else spec.nature_juridique)
    time.sleep(CALL_DELAY)
    if not cands and spec.nature_juridique:
        cands = _api_call(query, dept_code, None)
        time.sleep(CALL_DELAY)
    if not cands and dept_code:
        cands = _api_call(query, None, spec.nature_juridique)
        time.sleep(CALL_DELAY)

    score_ref = "sce departemental incendie secours sdis" if spec.query_key == "SDIS" else normalize_for_score(raw_name)
    scored = []
    for rank, cand in enumerate(cands, 1):
        siege = cand.get("siege") or {}
        scored.append(
            {
                "candidate_rank": rank,
                "candidate_siren": cand.get("siren"),
                "candidate_siret": siege.get("siret"),
                "candidate_name": cand.get("nom_complet"),
                "score": round(_score(score_ref, cand), 1),
            }
        )
    scored = sorted(scored, key=lambda x: x["score"], reverse=True)
    best = scored[0] if scored else {}
    second = scored[1]["score"] if len(scored) > 1 else None
    margin = (best.get("score", 0.0) - second) if second is not None else None
    high = bool(
        best
        and (
            best["score"] >= HIGH_SCORE
            or (best["score"] >= HIGH_SCORE_LOWER and len(scored) == 1)
            or (best["score"] >= HIGH_SCORE_LOWER and margin is not None and margin >= HIGH_MARGIN)
        )
    )
    result = {
        "buyer_name_raw": raw_name,
        "buyer_name_normalized": normalize_buyer_name(raw_name),
        "buyer_siren_enriched": best.get("candidate_siren") if high else None,
        "buyer_siret_enriched": best.get("candidate_siret") if high else None,
        "buyer_enrichment_source": "api_recherche_entreprises_current",
        "buyer_enrichment_confidence": "HIGH" if high else ("NO_MATCH" if not scored else "LOWER_CONFIDENCE"),
        "buyer_enrichment_status": "matched" if high else "not_upgraded",
        "buyer_enrichment_score": best.get("score"),
        "buyer_enrichment_margin": round(margin, 1) if margin is not None else None,
        "buyer_enrichment_candidate_count": len(scored),
        "buyer_enrichment_name": best.get("candidate_name"),
        "buyer_enrichment_note": f"query={query}",
    }
    cache[key] = result
    return result


def build_current_enrichment(df: pd.DataFrame, use_api: bool) -> pd.DataFrame:
    seed = load_seed_matches()
    seed_map = {}
    if not seed.empty:
        high = seed[seed["enrichment_confidence"].eq("HIGH") & seed["enriched_siren"].notna()].copy()
        seed_map = high.drop_duplicates("buyer_name_normalized").set_index("buyer_name_normalized").to_dict("index")

    buyers = (
        df.groupby("buyer_name_raw", dropna=False)
        .agg(
            buyer_name_normalized=("buyer_name_normalized", "first"),
            dept_code=("code_departement", lambda s: str(s.dropna().iloc[0]).split("|")[0] if s.dropna().size else None),
            n_notices=("idweb", "count"),
        )
        .reset_index()
    )
    cache_path = RAW_CURRENT / "sirene_current_cache.json"
    cache = load_cache(cache_path)
    rows = []
    for i, row in enumerate(buyers.itertuples(index=False), 1):
        seed_row = seed_map.get(row.buyer_name_normalized)
        if seed_row:
            rows.append(
                {
                    "buyer_name_raw": row.buyer_name_raw,
                    "buyer_name_normalized": row.buyer_name_normalized,
                    "buyer_siren_enriched": clean_siren(seed_row.get("enriched_siren")),
                    "buyer_siret_enriched": clean_siret(seed_row.get("enriched_siret")),
                    "buyer_enrichment_source": "previous_high_confidence_cache",
                    "buyer_enrichment_confidence": "HIGH",
                    "buyer_enrichment_status": "matched",
                    "buyer_enrichment_score": seed_row.get("enrichment_score"),
                    "buyer_enrichment_margin": seed_row.get("margin"),
                    "buyer_enrichment_candidate_count": seed_row.get("n_candidates"),
                    "buyer_enrichment_name": seed_row.get("enriched_name"),
                    "buyer_enrichment_note": "seeded from existing high-confidence buyer enrichment",
                }
            )
        elif use_api and isinstance(row.buyer_name_raw, str) and row.buyer_name_raw.strip():
            rows.append(classify_api_result(row.buyer_name_raw, row.dept_code, cache))
        else:
            rows.append(
                {
                    "buyer_name_raw": row.buyer_name_raw,
                    "buyer_name_normalized": row.buyer_name_normalized,
                    "buyer_siren_enriched": None,
                    "buyer_siret_enriched": None,
                    "buyer_enrichment_source": "not_attempted",
                    "buyer_enrichment_confidence": "NO_MATCH",
                    "buyer_enrichment_status": "not_upgraded",
                    "buyer_enrichment_score": None,
                    "buyer_enrichment_margin": None,
                    "buyer_enrichment_candidate_count": 0,
                    "buyer_enrichment_name": None,
                    "buyer_enrichment_note": "API enrichment disabled or missing buyer name",
                }
            )
        if i % 50 == 0:
            save_cache(cache_path, cache)
            print(f"  enriched buyer names {i}/{len(buyers)}")
    save_cache(cache_path, cache)
    out = pd.DataFrame(rows)
    out["_confidence_rank"] = out["buyer_enrichment_confidence"].map({"HIGH": 0, "LOWER_CONFIDENCE": 1, "NO_MATCH": 2}).fillna(3)
    out["_score_sort"] = pd.to_numeric(out["buyer_enrichment_score"], errors="coerce").fillna(-1)
    out = (
        out.sort_values(["buyer_name_raw", "buyer_name_normalized", "_confidence_rank", "_score_sort"], ascending=[True, True, True, False])
        .drop_duplicates(["buyer_name_raw", "buyer_name_normalized"], keep="first")
        .drop(columns=["_confidence_rank", "_score_sort"])
    )
    out.to_csv(PROCESSED_CURRENT / "current_buyer_siren_enrichment.csv", index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-api", action="store_true", help="Use only prior high-confidence cache and raw SIRET/SIREN.")
    args = parser.parse_args()

    ensure_dirs()
    flat_path = PROCESSED_CURRENT / "boamp_full_flat.csv"
    if not flat_path.exists():
        raise SystemExit(f"Missing {flat_path}; run scripts/download_boamp_current.py first.")
    df = pd.read_csv(flat_path, dtype=str, low_memory=False)
    taxonomy = pd.read_csv(PROCESSED_DIR / "taxonomy.csv", dtype=str)
    matcher = build_taxonomy_matcher(taxonomy)

    df["notice_id"] = df["idweb"].astype(str).str.strip()
    df["dateparution"] = pd.to_datetime(df["dateparution"], errors="coerce")
    df["year"] = df["dateparution"].dt.year
    df["nature"] = df["nature"].astype(str).str.strip().str.upper()
    df["buyer_name_raw"] = df["nomacheteur"]
    df["buyer_name_normalized"] = df["buyer_name_raw"].map(normalize_buyer_name)
    df["objet_clean"] = df["objet"].map(normalize_text)
    df["buyer_siret_raw"] = df.get("buyer_siret")
    df["buyer_siret_clean"] = df["buyer_siret_raw"].map(clean_siret)
    df["buyer_siren_raw"] = df.get("buyer_siren")
    df["buyer_siren_clean"] = df["buyer_siren_raw"].map(clean_siren) if "buyer_siren" in df.columns else None
    df["buyer_siren_from_siret"] = df["buyer_siret_clean"].map(lambda x: x[:9] if isinstance(x, str) else None)

    df["cpv_clean"] = df["cpv_principal"].map(clean_cpv)
    df["cpv_full8"] = df["cpv_clean"]
    df["cpv_div2"] = df["cpv_clean"].str[:2]
    df["cpv_group3"] = df["cpv_clean"].str[:3]
    df["cpv_class4"] = df["cpv_clean"].str[:4]
    df["cpv_category5"] = df["cpv_clean"].str[:5]
    df["cpv_is_missing"] = df["cpv_clean"].isna()
    df["cpv_is_generic"] = df["cpv_clean"].map(is_generic_cpv)

    amount_flags = apply_amount_flags(pd.to_numeric(df.get("amount_eur"), errors="coerce"))
    duration_flags = apply_duration_flags(pd.to_numeric(df.get("duration_months"), errors="coerce"))
    df = pd.concat([df, amount_flags, duration_flags], axis=1)
    df = df.rename(columns={"duration_raw": "duration_raw_boamp"})
    if "duration_clean" not in df.columns:
        df["duration_clean"] = pd.to_numeric(df.get("duration_months"), errors="coerce")
    df["duration_imputed_flag"] = df["duration_clean"].isna() | df["flag_duration_suspect"].fillna(False).astype(bool)

    tags = [matcher(c, o) for c, o in zip(df["cpv_clean"], df["objet"])]
    df["category_id"] = [t[0] for t in tags]
    df["category_label"] = [t[1] for t in tags]

    enrichment = build_current_enrichment(df, use_api=not args.no_api)
    df = df.merge(
        enrichment,
        on=["buyer_name_raw", "buyer_name_normalized"],
        how="left",
        validate="many_to_one",
    )
    df["buyer_siren_enriched"] = df["buyer_siren_enriched"].map(clean_siren)
    key_parts = [
        buyer_key_from_parts(siret, siren, siren_from_siret, enriched, name)
        for siret, siren, siren_from_siret, enriched, name in zip(
            df["buyer_siret_clean"],
            df["buyer_siren_clean"],
            df["buyer_siren_from_siret"],
            df["buyer_siren_enriched"],
            df["buyer_name_normalized"],
        )
    ]
    df["buyer_key"] = [x[0] for x in key_parts]
    df["buyer_key_type"] = [x[1] for x in key_parts]
    df["buyer_key_source"] = [x[2] for x in key_parts]
    df["raw_trace_id"] = "BOAMP:" + df["notice_id"].astype(str)

    out_path = PROCESSED_CURRENT / "boamp_full_clean_enriched.csv"
    df.to_csv(out_path, index=False)

    n = len(df)
    summary = pd.DataFrame(
        [
            {"metric": "records", "value": n},
            {"metric": "APPEL_OFFRE", "value": int(df["nature"].eq("APPEL_OFFRE").sum())},
            {"metric": "ATTRIBUTION", "value": int(df["nature"].eq("ATTRIBUTION").sum())},
            {"metric": "valid_siret_rows", "value": int(df["buyer_siret_clean"].notna().sum())},
            {"metric": "enriched_siren_rows", "value": int(df["buyer_siren_enriched"].notna().sum())},
            {"metric": "name_fallback_rows", "value": int(df["buyer_key_type"].eq("NAME").sum())},
        ]
    )
    summary.to_csv(TABLES_DATA / "buyer_enrichment_summary.csv", index=False)
    (
        df.groupby("buyer_key_type", dropna=False)
        .agg(rows=("notice_id", "count"), buyers=("buyer_key", "nunique"))
        .reset_index()
        .to_csv(TABLES_DATA / "buyer_key_quality_summary.csv", index=False)
    )
    (
        df.groupby("year", dropna=False)
        .agg(
            rows=("notice_id", "count"),
            valid_siret_rows=("buyer_siret_clean", lambda s: s.notna().sum()),
            enriched_siren_rows=("buyer_siren_enriched", lambda s: s.notna().sum()),
            siren_or_siret_key_rows=("buyer_key_type", lambda s: s.isin(["SIRET", "SIREN", "SIREN_FROM_SIRET", "SIREN_ENRICHED"]).sum()),
        )
        .reset_index()
        .to_csv(TABLES_DATA / "siren_siret_coverage_by_year.csv", index=False)
    )
    (
        df.groupby("year", dropna=False)
        .agg(rows=("notice_id", "count"), missing_cpv=("cpv_is_missing", "sum"), generic_cpv=("cpv_is_generic", "sum"))
        .reset_index()
        .to_csv(TABLES_DATA / "cpv_quality_by_year.csv", index=False)
    )
    (
        df.groupby("year", dropna=False)
        .agg(rows=("notice_id", "count"), duration_clean=("duration_clean", lambda s: s.notna().sum()), duration_imputed_or_suspect=("duration_imputed_flag", "sum"))
        .reset_index()
        .to_csv(TABLES_DATA / "duration_quality_by_year.csv", index=False)
    )
    append_run_log(
        [
            "",
            f"## Current clean/enrichment - {utc_now()}",
            f"- Output: {out_path}",
            f"- Records: {n}",
            f"- APPEL_OFFRE: {int(df['nature'].eq('APPEL_OFFRE').sum())}",
            f"- Buyer key types: {df['buyer_key_type'].value_counts().to_dict()}",
        ]
    )
    print("=== Current enriched dataset ===")
    print(f"Rows: {n}")
    print(f"APPEL_OFFRE: {int(df['nature'].eq('APPEL_OFFRE').sum())}")
    print(f"Buyer key types: {df['buyer_key_type'].value_counts().to_dict()}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
