"""TASK 2 — BOAMP field profiling.

Reads the full flattened BOAMP dataset produced by Task 1b and produces a
field-by-field profiling table (dtype, completeness, cardinality, sample
values, notes), plus targeted deep-dives on the five critical fields named in
the brief: SIRET, CPV, amount, duration, notification vs award dates.

Outputs:
  data/processed/boamp_field_profile.csv
  data/processed/boamp_field_profile.md
  (deep-dive statistics printed to stdout, reused in the Week-1 report)
"""

import pandas as pd

from utils import PROCESSED_DIR, profile_dataframe, to_markdown_table

# Free-text notes attached to each field in the profiling table.
FIELD_NOTES = {
    "idweb": "BOAMP notice identifier (YY-NNNNNN); unique key, always present.",
    "dateparution": "Publication date on BOAMP; the only universally present date.",
    "datelimitereponse": "Offer deadline; only meaningful for contract notices.",
    "nomacheteur": "Buyer name, free text; many spelling variants per buyer.",
    "code_departement": "Department list ('|'-joined); JOUE notices may list all 5 PdL departments.",
    "famille": "JOUE (EU threshold) vs FNS (national); drives form completeness.",
    "nature": "APPEL_OFFRE / ATTRIBUTION / RECTIFICATIF…; structured code.",
    "type_procedure": "Structured procedure code (OUVERT, PROCEDURE_ADAPTE…).",
    "descripteur_libelle": "BOAMP in-house thesaurus, NOT CPV; well filled.",
    "objet": "Free-text contract object; main NLP input for Phase 2.",
    "titulaire": "Winning supplier name(s); award notices only.",
    "annonce_lie": "Linked notice idwebs; key for AAPC<->award linking (Week 3).",
    "donnees_format": "legacy (pre-2024 forms) vs eforms (EU UBL, 2024+).",
    "cpv_principal": "Main CPV; structured code, see specificity deep-dive.",
    "cpv_all": "Main + per-lot CPV codes ('|'-joined).",
    "buyer_siret": "Buyer SIRET; almost only present in eForms notices (2024+).",
    "amount_eur": "Estimated or awarded amount; see deep-dive (0/ceiling values).",
    "duration_months": "Declared duration normalized to months; see Task 5.",
    "duration_source_field": "Original field the duration came from.",
    "date_attribution": "Award date; award notices only, placeholder dates excluded.",
    "date_publication_anterieure": "Publication date of the original contract notice, as recalled inside award notices.",
}


def main() -> None:
    df = pd.read_csv(PROCESSED_DIR / "boamp_full_flat.csv",
                     dtype={"buyer_siret": str, "buyer_cp": str,
                            "cpv_principal": str})

    # ---- generic profiling table -----------------------------------------
    profile = profile_dataframe(df, notes=FIELD_NOTES)
    profile.to_csv(PROCESSED_DIR / "boamp_field_profile.csv", index=False)
    (PROCESSED_DIR / "boamp_field_profile.md").write_text(
        f"# BOAMP field profile ({len(df)}-notice full dataset, PdL, 2015-2024)\n\n"
        + to_markdown_table(profile) + "\n")
    print("=== BOAMP field profile (saved to data/processed/) ===")
    print(profile.to_string(index=False, max_colwidth=40))

    # ---- deep-dive 1: SIRET/SIREN ----------------------------------------
    print("\n=== Deep-dive: buyer SIRET/SIREN ===")
    siret = df["buyer_siret"].dropna()
    print(f"present: {len(siret)}/{len(df)} ({100*len(siret)/len(df):.1f}%)")
    print("by donnees format:")
    print(df.groupby("donnees_format")["buyer_siret"]
            .apply(lambda s: f"{s.notna().mean():.1%}").to_string())
    lengths = siret.str.len().value_counts()
    print(f"length distribution (14=SIRET, 9=SIREN): {lengths.to_dict()}")

    # ---- deep-dive 2: CPV specificity -------------------------------------
    print("\n=== Deep-dive: CPV codes ===")
    cpv = df["cpv_principal"].dropna()
    print(f"main CPV present: {len(cpv)}/{len(df)} ({100*len(cpv)/len(df):.1f}%)")
    generic = cpv[cpv.str.match(r"^\d{2}0{6}$")]  # e.g. 72000000, division only
    print(f"generic division-level codes (XX000000): {len(generic)}/{len(cpv)} "
          f"({100*len(generic)/len(cpv):.1f}%)  e.g. {generic.unique()[:5]}")
    print("top CPV divisions:", cpv.str[:2].value_counts().head(6).to_dict())

    # ---- deep-dive 3: amounts ---------------------------------------------
    print("\n=== Deep-dive: amounts ===")
    amount = df["amount_eur"]
    print(f"present: {amount.notna().sum()}/{len(df)} "
          f"({amount.notna().mean():.1%})")
    print(f"zero values: {(amount == 0).sum()}")
    print(f"suspicious >= 10M EUR (possible ceiling/aggregate): "
          f"{(amount >= 1e7).sum()}")
    print("by nature:")
    print(df.groupby("nature")["amount_eur"]
            .apply(lambda s: f"{s.notna().mean():.1%}").to_string())
    print(amount.describe().to_string())

    # ---- deep-dive 4: duration --------------------------------------------
    print("\n=== Deep-dive: declared duration ===")
    dur = df["duration_months"]
    print(f"present: {dur.notna().sum()}/{len(df)} ({dur.notna().mean():.1%})")
    print("source field:", df["duration_source_field"].value_counts().to_dict())
    print("by nature:")
    print(df.groupby("nature")["duration_months"]
            .apply(lambda s: f"{s.notna().mean():.1%}").to_string())

    # ---- deep-dive 5: dates -----------------------------------------------
    print("\n=== Deep-dive: notification vs award dates ===")
    print(f"dateparution present:      {df['dateparution'].notna().mean():.1%}")
    print(f"date_attribution present:  {df['date_attribution'].notna().mean():.1%} "
          f"(award notices only: "
          f"{df.loc[df.nature=='ATTRIBUTION','date_attribution'].notna().mean():.1%})")
    print(f"date_publication_anterieure present: "
          f"{df['date_publication_anterieure'].notna().mean():.1%} "
          f"(among award notices: "
          f"{df.loc[df.nature=='ATTRIBUTION','date_publication_anterieure'].notna().mean():.1%})")
    both = df[df["date_attribution"].notna()
              & df["date_publication_anterieure"].notna()]
    print(f"records with BOTH original-publication and award dates: {len(both)}")


if __name__ == "__main__":
    main()
