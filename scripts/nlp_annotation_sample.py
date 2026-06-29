"""
Phase 2 NLP — Step 0: Annotation Sampling

Produces data/annotation/boamp_annotation_sample.csv (350 rows, stratified by category).
The user fills the `category_id_final` column and saves as boamp_annotation_gold.csv.
"""

import random
import pandas as pd

SEED = 42
OUTPUT = "data/annotation/boamp_annotation_sample.csv"

# Target counts per category
TARGETS = {
    "CAT01": 35,  # Software & Applications
    "CAT02": 35,  # IT Services & Consulting
    "CAT03": 30,  # Cybersecurity
    "CAT04": 35,  # Telecom & Networks
    "CAT05": 25,  # Cloud & Infrastructure (only 41 total)
    "CAT06": 25,  # IT Hardware & Equipment (only 73 total)
    "CAT07": 25,  # Digital Workplace
    "CAT08": 25,  # Data & AI (only 76 total)
    "CAT09": 14,  # GIS & Mapping — take all (only 14)
    "CAT10": 31,  # IT Maintenance (only 54 total)
    "CAT_UNKNOWN": 50,  # Unknown — most informative for the classifier
}
# Total target: ~330 rows (some categories are smaller than target)

EXPORT_COLS = [
    "idweb",
    "objet",
    "descripteur_libelle",
    "cpv_clean",
    "cpv_div2",
    "category_id_rule",
    "category_label_rule",
    "category_id_final",
    "notes",
]

LABEL_HINT = """
Valid category IDs:
  CAT01  Software & Applications
  CAT02  IT Services & Consulting
  CAT03  Cybersecurity
  CAT04  Telecom & Networks
  CAT05  Cloud & Infrastructure
  CAT06  IT Hardware & Equipment
  CAT07  Digital Workplace & Collaboration
  CAT08  Data & AI
  CAT09  GIS & Mapping
  CAT10  IT Maintenance & Support
"""


def main():
    df = pd.read_csv("data/processed/boamp_full_clean.csv", low_memory=False)

    # Keep only rows with usable text
    df = df[df["objet"].notna() & (df["objet"].str.strip() != "")].copy()

    # Rename existing rule-based labels for clarity
    df = df.rename(columns={"category_id": "category_id_rule", "category_label": "category_label_rule"})

    random.seed(SEED)
    frames = []

    for cat_id, target in TARGETS.items():
        pool = df[df["category_id_rule"] == cat_id]
        n = min(target, len(pool))
        if n == 0:
            print(f"  WARNING: no rows for {cat_id}")
            continue
        sampled = pool.sample(n=n, random_state=SEED)
        frames.append(sampled)
        print(f"  {cat_id}: sampled {n} / {len(pool)} available")

    sample = pd.concat(frames, ignore_index=True).sample(frac=1, random_state=SEED)

    # Add empty annotation columns
    sample["category_id_final"] = ""
    sample["notes"] = ""

    out = sample[EXPORT_COLS]
    out.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    print(f"\nSaved {len(out)} rows to {OUTPUT}")
    print(LABEL_HINT)
    print("Next step: open the CSV, fill 'category_id_final' for each row,")
    print("then save as data/annotation/boamp_annotation_gold.csv")


if __name__ == "__main__":
    main()
