"""TASK 4 — BOAMP vs DECP side-by-side comparison.

Computes completion rates for a harmonized set of fields directly from the
two flattened samples (Tasks 1 and 3), then writes the comparison table and
the primary-source recommendation paragraph.

Outputs:
  data/processed/source_comparison.csv
  data/processed/source_comparison.md
"""

import pandas as pd

from utils import PROCESSED_DIR, to_markdown_table

# Harmonized field -> (BOAMP column, DECP column). None = field absent.
FIELD_MAP = {
    "Buyer SIRET": ("buyer_siret", "acheteur_id"),
    "Buyer name": ("nomacheteur", "acheteur_nom"),
    "Contract object (text)": ("objet", "objet"),
    "CPV code": ("cpv_principal", "codeCPV"),
    "Amount (EUR)": ("amount_eur", "montant"),
    "Contract duration": ("duration_months", "dureeMois"),
    "Notification date": (None, "dateNotification"),
    "Publication date": ("dateparution", "datePublicationDonnees"),
    "Award date": ("date_attribution", None),
    "Winner identity": ("titulaire", "titulaire_id"),
    "Procedure type": ("type_procedure", "procedure"),
    "Offers received": (None, "offresRecues"),
    "Notice type (AAPC/award)": ("nature", None),
    "Linked notices (renewal hints)": ("annonce_lie", None),
}

# Recommendation + justification per harmonized field (informed by the
# Task 2 / Task 3 deep-dives; completion percentages are computed live).
RECOMMENDATIONS = {
    "Buyer SIRET": ("DECP", "Mandatory 14-digit SIRET in DECP; in BOAMP only "
                            "eForms notices (2024+) carry it."),
    "Buyer name": ("Both", "BOAMP has the declared name (free text, "
                           "variants); the tabular DECP adds a "
                           "SIRENE-normalized name — useful join key."),
    "Contract object (text)": ("BOAMP", "Longer, richer text in BOAMP (NLP "
                               "input for Phase 2); DECP object is terse."),
    "CPV code": ("Both", "Well filled in both; cross-check to fix generic "
                         "division-level codes."),
    "Amount (EUR)": ("DECP", "Mandatory in DECP; in BOAMP mostly on award "
                             "notices only and format-dependent."),
    "Contract duration": ("DECP", "dureeMois is a mandatory DECP field; BOAMP "
                          "declares it on ~3/4 of contract notices only."),
    "Notification date": ("DECP", "Only DECP has the actual notification "
                          "date — the survival-analysis time origin."),
    "Publication date": ("BOAMP", "BOAMP dateparution is universal and "
                         "reliable; DECP publication date can lag years."),
    "Award date": ("BOAMP", "Award notices carry DATE_ATTRIBUTION (95%); "
                            "absent from DECP."),
    "Winner identity": ("Both", "BOAMP gives the name, DECP the SIRET; "
                                "complementary."),
    "Procedure type": ("Both", "Structured in both sources."),
    "Offers received": ("DECP", "DECP-only field (filled on ~1/4 of rows); "
                                "useful competition signal."),
    "Notice type (AAPC/award)": ("BOAMP", "Notice-level granularity (AAPC, "
                                 "award, rectif.) exists only in BOAMP."),
    "Linked notices (renewal hints)": ("BOAMP", "annonce_lie links award to "
                                       "original notice; key for Week 3."),
}


def completion(df: pd.DataFrame, col: str | None) -> float | None:
    """Completion rate (%) of one column; None when the field is absent."""
    if col is None or col not in df.columns:
        return None
    series = df[col]
    filled = series.notna() & (series.astype(str).str.strip() != "")
    return round(100 * filled.mean(), 1)


def availability(rate: float | None) -> str:
    if rate is None:
        return "No"
    return "Yes" if rate >= 80 else "Partial"


def main() -> None:
    boamp = pd.read_csv(PROCESSED_DIR / "boamp_sample_flat.csv")
    decp = pd.read_csv(PROCESSED_DIR / "decp_sample_flat.csv")

    rows = []
    for field, (bcol, dcol) in FIELD_MAP.items():
        b_rate, d_rate = completion(boamp, bcol), completion(decp, dcol)
        rec, why = RECOMMENDATIONS[field]
        rows.append({
            "Field": field,
            "BOAMP availability": availability(b_rate),
            "BOAMP completion %": b_rate if b_rate is not None else "—",
            "DECP availability": availability(d_rate),
            "DECP completion %": d_rate if d_rate is not None else "—",
            "Recommended source": rec,
            "Justification": why,
        })
    table = pd.DataFrame(rows)
    table.to_csv(PROCESSED_DIR / "source_comparison.csv", index=False)

    recommendation = (
        "**Primary-source recommendation.** BOAMP should be the primary source "
        "for the internship corpus: it is the only source that covers the full "
        "2015-2024 period, distinguishes contract notices from award notices "
        "(the event structure survival analysis needs), provides the richest "
        "free-text objects for NLP, and links award notices back to the "
        "original call (annonce_lie), which Week 3's renewal linking will "
        "build on. DECP (tabular decp.parquet) should be used as the "
        "enrichment source from 2019 onwards: joined on buyer SIRET/name + "
        "object/CPV similarity, it supplies the fields BOAMP lacks or fills "
        "poorly — mandatory buyer SIRET, SIRENE-normalized buyer name, "
        "amount, dureeMois and, crucially, the notification date that "
        "defines the survival-time origin. Its in-scope volume (3,039 "
        "digital PdL contracts, 2018-2024) already approaches the 2,000-"
        "5,000-contract corpus target on its own. The join is still "
        "non-trivial (BOAMP legacy notices carry no SIRET) and should be "
        "prototyped in Week 2."
    )

    md = ("# BOAMP vs DECP comparison\n\n" + to_markdown_table(table)
          + "\n\n" + recommendation + "\n")
    (PROCESSED_DIR / "source_comparison.md").write_text(md)

    print(table.to_string(index=False, max_colwidth=45))
    print("\n" + recommendation)
    print(f"\nSaved to {PROCESSED_DIR / 'source_comparison.csv'} and .md")


if __name__ == "__main__":
    main()
