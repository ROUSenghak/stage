# Week 1 Summary Report – Data Exploration

**Date:** 2026-06-11
**Intern:** ROU Senghak

## 1. Data Sources Explored

We explored the two open data sources of French public procurement and built one working
sample from each, within the internship scope (digital contracts: CPV 48/72/32/35; Pays de
la Loire; 2015–2024).

**BOAMP.** We queried the Opendatasoft Explore API (`boamp-datadila.opendatasoft.com`,
dataset `boamp`; `api.boamp.fr` redirects there). The dataset contains 1,675,576 notices
nationally, of which **83,920** match the five PdL departments (44/49/53/72/85) since 2015.
We collected a sample of **500 digital notices**, stratified at exactly 50 per year
2015–2024, by combining a server-side CPV pre-filter with client-side verification. The
sample mixes 225 contract notices (AAPC), 217 award notices, and 58 other notices
(rectifications, modifications, prior information). All 117 raw API pages are kept verbatim
in `data/raw/boamp_sample/`.

**DECP.** DECP has no queryable API. We first parsed the official consolidated JSON files
(`decp-2022.json`, 21 MB; `decp-2024.json`, 524 MB, streamed with ijson): this first pass
yielded only 512 in-scope contracts, 396 of them notified in 2024 (see §3.3). We therefore
switched to the **tabular consolidation `decp.parquet`** (210 MB, updated daily,
3,075,779 rows, SIRENE-enriched, built by the decp-processing project from the official
files). After filtering on digital CPV + PdL buyer department + 2015–2024 + current
versions (`donneesActuelles`), we obtained **3,039 contracts**
(`data/processed/decp_sample_flat.csv`).

| Sample | Records | Period covered | Departments (44/49/72/85/53) | CPV divisions (72/48/32/35) |
|---|---|---|---|---|
| BOAMP | 500 | 50/year, 2015–2024 | multi-dept notices: 46/500 also list non-PdL areas | 218 / 89 / 75 / 40 (main code) |
| DECP | 3,039 | 42 (2018), 361–574/year 2019–2024 | 1,438 / 528 / 508 / 362 / 203 | 1,586 / 636 / 595 / 222 |

## 2. Available Fields and Completion Rates

We profiled every field of both samples with a common procedure (completion rate,
cardinality, sample values). The table below summarizes the fields that matter for the
internship; full tables are in `data/processed/boamp_field_profile.csv`,
`decp_field_profile.csv` and `source_comparison.csv`.

| Field | BOAMP (n=500) | DECP (n=3,039) | Preferred |
|---|---|---|---|
| Buyer SIRET | 8.0% (100% of 2024 eForms, 0% before) | **100%** (14-digit) | DECP |
| Buyer name | **100%** (declared, spelling variants) | 100% (SIRENE-normalized) | both |
| Contract object (text) | **100%** (rich, avg. longer) | 99.9% (terse) | BOAMP |
| CPV code | 97.8% (12.5% generic `XX000000`) | **100%** | both |
| Amount (EUR) | 44.6% (79.3% of awards, 21.3% of AAPC) | **95.6%** | DECP |
| Contract duration | 34.4% (74.2% of AAPC, 0.9% of awards) | **99.4%** (`dureeMois`) | DECP |
| Notification date | absent | **100%** | DECP |
| Publication date | **100%** (`dateparution`) | 98.0% (can lag years behind) | BOAMP |
| Award date | 94.9% of award notices | absent | BOAMP |
| Offers received | absent | 26.4% | DECP |
| Notice type + linked notices | **100%** (`nature`); `annonce_lie` 46.2% | absent | BOAMP |

## 3. Key Data Quality Observations

1. **BOAMP changed format in 2024 (eForms).** From 2024 the `donnees` payload switches
   from the legacy BOAMP forms to the EU eForms/UBL structure. The impact is measurable:
   our legacy-only CPV pre-filter matched 3,691 PdL notices in 2023 but only 242 in 2024;
   after we added eForms support, 2024 was sampled normally (50/50). Side effects we
   verified: buyer SIRET exists only in eForms notices (40/40 vs 0/460 legacy), and eForms
   uses the placeholder award date `2000-01-01`, which we exclude.
2. **CPV codes are present but partly generic.** 489/500 BOAMP notices (97.8%) carry a
   main CPV, but 61/489 (12.5%) are division-level only (e.g. `72000000`), and 11 notices
   (2.2%) have no CPV at all (national FNS forms).
3. **The official DECP consolidated JSONs are not per-year censuses.** The vintages differ
   in size (21 MB for 2022 vs 524 MB for 2024) and even in layout (`marches: [...]` vs
   `marches.marche: [...]`); our first pass found only 512 in-scope contracts, 77% of them
   notified in 2024. The tabular `decp.parquet` raises this to 3,039 contracts, dense from
   2019 (361–574/year). Before 2018, DECP is empty whatever the file: the 2015–2017
   history exists only in BOAMP.
4. **Location codes are full of traps.** In DECP, `lieuExecution.code` mixes postal,
   commune, department and region codes: we removed 18 false positives where code "44"
   typed *Code région* meant pre-2016 Lorraine, not Loire-Atlantique, and now filter on
   the SIRENE-derived buyer department instead. In BOAMP, 46/500 notices are
   multi-department contracts also covering non-PdL areas (each still includes ≥1 PdL
   department).
5. **Amounts need cleaning rules in both sources.** BOAMP: 44.6% filled, median €432k but
   max €932M, and 5 values ≥ €10M look like ceilings or aggregated lot totals. DECP: 95.6%
   filled, median €100k, but 31 zero values, 51 values below €1k, and 23 values ≥ €10M
   (max €1.0B).

## 4. Source Decision

We retain **BOAMP as the primary source**. It is the only source covering the full
2015–2024 period (DECP starts in 2018), the only one that distinguishes contract notices
from award notices — the event structure survival analysis needs — and the only one that
links an award back to its original call (`annonce_lie`, 46.2% of the sample), which is
the starting point of the Week-3 renewal linking. Its free-text objects are also the
richest input for the Phase-2 NLP classification.

We use **DECP (`decp.parquet`) as the enrichment source from 2019 onwards**. Joined on
buyer SIRET/name + CPV + object similarity, it contributes exactly the fields BOAMP fills
poorly: buyer SIRET (100% vs 8%), amount (95.6% vs 44.6%), duration (99.4% vs 34.4%) and,
crucially, the **notification date** (100% vs absent), which is the natural survival-time
origin. Its in-scope volume alone (3,039 contracts) already approaches the
2,000–5,000-contract corpus target of the internship guide. The join is non-trivial —
legacy BOAMP notices carry no SIRET — and we will prototype it in Week 2.

## 5. Scientific Question – Contract Duration Reliability

We measured the reliability of the declared contract duration on the BOAMP sample. The
field is filled on **172/500 notices (34.4%)** — it is essentially a contract-notice field
(74.2% of AAPC vs 0.9% of award notices). Where present, it is coarse: **121/172 (70.3%)**
of values are exactly 12, 24, 36 or 48 months and **135/172 (78.5%)** are whole-year
multiples (median 24, IQR 12–48, max 360 months; histogram in `reports/figures/`). Buyers
evidently declare an administrative maximum (base period + renewals), not an expected
lifetime. We then tried to confront declared and observed durations within BOAMP: declared
duration and award date never coexist in a single notice (0/500), so the comparison is
structurally impossible; the only computable gap — original publication → award, on 102
linked pairs — has a median of **4.3 months** (IQR 3.0–6.1) and measures the procurement
*procedure*, not the contract life. **We therefore recommend:** (i) not using the declared
duration as the survival target; (ii) building the target as the observed time between
successive notices of the same buyer/segment (Week-3 linking); (iii) keeping the declared
duration as a covariate and as a prior for the renewal search window (declared ± 6 months);
(iv) cross-checking it against DECP's `dureeMois` where a match exists — noting that
`dureeMois` shows the same coarseness (65.9% exactly 12/24/36/48 months), so it validates
presence, not precision.

## 6. Open Questions and Risks

1. **BOAMP↔DECP join feasibility** — without SIRET on 92% of BOAMP notices, the match must
   rely on buyer-name normalization + CPV + dates; precision/recall unknown (Week-2 test).
2. **eForms extraction coverage** — our eForms parsing (CPV, SIRET, duration, amount,
   dates) was validated on the 50 sampled 2024 notices; it must be re-validated on a larger
   pull, and the `2000-01-01` placeholder-date rate quantified.
3. **Dependence on a community-maintained DECP transformation** — `decp.parquet`
   (decp-processing) is far more usable than the official JSONs, but it is not the primary
   source: we should spot-check its de-duplication (`donneesActuelles`) and SIRENE joins
   against the official files on a sample before freezing the corpus (Week 2–3).
