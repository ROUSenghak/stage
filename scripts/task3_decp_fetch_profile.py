"""TASK 3 — DECP dataset exploration.

Downloads the DECP (Données Essentielles de la Commande Publique) in its
consolidated **tabular form** (decp.parquet, ~210 MB, updated daily on
data.gouv.fr), filters it to the internship scope (digital CPV 48/72/32/35,
Pays de la Loire buyers, 2015-2024) and profiles the result with the same
profiling function as BOAMP (Task 2).

Why this file rather than the official JSON "fichiers consolidés":
  - Week-1 exploration showed the official yearly JSON vintages are
    inconsistent in size (decp-2022.json = 21 MB vs decp-2024.json = 524 MB)
    and even in layout ({"marches": [...]} vs {"marches": {"marche": [...]}}),
    and each vintage contains what was consolidated then, not a per-year
    census.
  - decp.parquet (dataset "DECP consolidées - format tabulaire", built by the
    decp-processing project from the official files) is a single flat table
    of the full history (~3.1M rows), de-duplicated via the donneesActuelles
    flag, and *enriched* with SIRENE joins: buyer/winner names, commune,
    department and region — fields the raw DECP does not carry.
  Caveat (documented): it is a community-maintained transformation of the
  official data, not the primary source itself.

Known coverage limitation: DECP is dense only from 2019 onwards (the format
was standardized in 2018); 2015-2017 is near-empty whatever the file used.

Outputs:
  data/raw/decp/decp.parquet              (raw download, git-ignored)
  data/processed/decp_sample_flat.csv     (filtered scope)
  data/processed/decp_field_profile.csv / .md
"""

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import requests

from utils import (
    RAW_DECP_DIR, PROCESSED_DIR, PDL_DEPARTMENTS, DIGITAL_CPV_PREFIXES,
    profile_dataframe, to_markdown_table,
)

# Stable "latest version" URL of decp.parquet on data.gouv.fr
# (dataset: donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire)
DECP_PARQUET_URL = (
    "https://www.data.gouv.fr/api/1/datasets/r/"
    "11cea8e8-df3e-4ed1-932b-781e2635e432"
)

# Columns kept for Week-1 profiling (the full table has ~58 columns).
COLUMNS = [
    "uid", "id", "nature", "objet", "codeCPV", "procedure",
    "dureeMois", "dateNotification", "datePublicationDonnees", "montant",
    "offresRecues", "donneesActuelles", "sourceDataset",
    "acheteur_id", "acheteur_nom", "acheteur_departement_code",
    "acheteur_categorie",
    "titulaire_id", "titulaire_typeIdentifiant", "titulaire_nom",
    "lieuExecution_code", "lieuExecution_typeCode",
]

FIELD_NOTES = {
    "uid": "Globally unique row id (acheteur_id + contract id).",
    "id": "Contract identifier (buyer-assigned, not globally unique).",
    "nature": "Marché / Marché subséquent / Marché de partenariat…",
    "objet": "Free-text contract object; terser than BOAMP's.",
    "codeCPV": "Single CPV code; structured.",
    "procedure": "Procedure label, standardized vocabulary.",
    "dureeMois": "Contract duration in months; mandatory DECP field.",
    "dateNotification": "Contract notification date; mandatory DECP field — survival-time origin.",
    "datePublicationDonnees": "Open-data publication date (can lag years).",
    "montant": "Contract amount EUR; mandatory; watch aberrant lows/ceilings.",
    "offresRecues": "Number of offers received.",
    "donneesActuelles": "True = current version of the contract (modifications collapsed).",
    "sourceDataset": "Upstream publishing platform (PES, AIFE, AWS…).",
    "acheteur_id": "Buyer SIRET (14 digits); mandatory DECP field.",
    "acheteur_nom": "Buyer name (SIRENE enrichment by decp-processing).",
    "acheteur_departement_code": "Buyer department (SIRENE enrichment) — used for the PdL filter.",
    "acheteur_categorie": "Buyer category (SIRENE enrichment).",
    "titulaire_id": "Winner identifier (SIRET mostly).",
    "titulaire_typeIdentifiant": "Identifier type of the winner (SIRET/TVA/HORS-UE…).",
    "titulaire_nom": "Winner name (SIRENE enrichment).",
    "lieuExecution_code": "Execution location code (postal/commune/department/région…).",
    "lieuExecution_typeCode": "Type of the location code — beware: région '44' = pre-2016 Lorraine.",
}


def download(url: str, path: Path) -> Path:
    """Stream-download decp.parquet (skipped if already cached)."""
    if path.exists() and path.stat().st_size > 0:
        print(f"{path.name}: already downloaded ({path.stat().st_size/1e6:.0f} MB)")
        return path
    print(f"Downloading {path.name} …")
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    print(f"  saved {path.stat().st_size/1e6:.0f} MB")
    return path


def main() -> None:
    RAW_DECP_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        path = download(DECP_PARQUET_URL, RAW_DECP_DIR / "decp.parquet")
    except requests.RequestException as err:
        # Documented fallback: official JSON "fichiers consolidés" on
        # data.gouv.fr (heavier and schema-inconsistent, see module docstring).
        raise SystemExit(f"!! download failed: {err} — fall back to the "
                         f"official consolidated JSON files")

    # Column-pruned read keeps memory reasonable (~3.1M rows x 22 cols).
    df = pq.read_table(path, columns=COLUMNS).to_pandas()
    total = len(df)

    # ---- internship scope filter ------------------------------------------
    cpv = df["codeCPV"].astype(str).str.split("-").str[0]  # drop check digit
    digital = cpv.str.startswith(DIGITAL_CPV_PREFIXES)
    pdl = df["acheteur_departement_code"].isin(PDL_DEPARTMENTS)
    year = pd.to_datetime(df["dateNotification"], errors="coerce").dt.year
    in_period = year.between(2015, 2024)
    current = df["donneesActuelles"].eq(True)  # keep current versions only

    df = df[digital & pdl & in_period & current].copy()
    df["codeCPV"] = cpv[df.index]
    print(f"decp.parquet: {total} rows scanned -> {len(df)} in scope "
          f"(digital CPV + PdL buyer + 2015-2024 + current version)")

    out = PROCESSED_DIR / "decp_sample_flat.csv"
    df.to_csv(out, index=False)
    print(f"Saved {out}")

    # ---- profile with the same function as BOAMP --------------------------
    profile = profile_dataframe(df, notes=FIELD_NOTES)
    profile.to_csv(PROCESSED_DIR / "decp_field_profile.csv", index=False)
    (PROCESSED_DIR / "decp_field_profile.md").write_text(
        "# DECP field profile (digital contracts, PdL buyers, 2015-2024)\n\n"
        + to_markdown_table(profile) + "\n")
    print("\n=== DECP field profile ===")
    print(profile.to_string(index=False, max_colwidth=40))

    # ---- scope stats -------------------------------------------------------
    print("\nContracts per notification year:")
    print(pd.to_datetime(df["dateNotification"], errors="coerce").dt.year
            .value_counts().sort_index().to_string())
    print("\nCPV divisions:", df["codeCPV"].str[:2].value_counts().to_dict())
    print("\nBuyer departments:",
          df["acheteur_departement_code"].value_counts().to_dict())
    print("\nBuyer SIRET length:",
          df["acheteur_id"].astype(str).str.len().value_counts().to_dict())
    amount = pd.to_numeric(df["montant"], errors="coerce")
    print("\nAmount: zero values:", int((amount == 0).sum()),
          "| < 1k EUR:", int((amount < 1e3).sum()),
          "| >= 10M EUR:", int((amount >= 1e7).sum()))
    print(amount.describe().to_string())
    dur = pd.to_numeric(df["dureeMois"], errors="coerce")
    print("\ndureeMois: exactly 12/24/36/48:",
          f"{dur.isin([12, 24, 36, 48]).mean():.1%}",
          "| whole-year multiples:", f"{(dur % 12 == 0).mean():.1%}")


if __name__ == "__main__":
    main()
