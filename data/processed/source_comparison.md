# BOAMP vs DECP comparison

| Field | BOAMP availability | BOAMP completion % | DECP availability | DECP completion % | Recommended source | Justification |
|---|---|---|---|---|---|---|
| Buyer SIRET | Partial | 8.0 | Yes | 100.0 | DECP | Mandatory 14-digit SIRET in DECP; in BOAMP only eForms notices (2024+) carry it. |
| Buyer name | Yes | 100.0 | Yes | 100.0 | Both | BOAMP has the declared name (free text, variants); the tabular DECP adds a SIRENE-normalized name — useful join key. |
| Contract object (text) | Yes | 100.0 | Yes | 99.9 | BOAMP | Longer, richer text in BOAMP (NLP input for Phase 2); DECP object is terse. |
| CPV code | Yes | 97.8 | Yes | 100.0 | Both | Well filled in both; cross-check to fix generic division-level codes. |
| Amount (EUR) | Partial | 44.6 | Yes | 95.6 | DECP | Mandatory in DECP; in BOAMP mostly on award notices only and format-dependent. |
| Contract duration | Partial | 34.4 | Yes | 99.4 | DECP | dureeMois is a mandatory DECP field; BOAMP declares it on ~3/4 of contract notices only. |
| Notification date | No | — | Yes | 100.0 | DECP | Only DECP has the actual notification date — the survival-analysis time origin. |
| Publication date | Yes | 100.0 | Yes | 98.0 | BOAMP | BOAMP dateparution is universal and reliable; DECP publication date can lag years. |
| Award date | Partial | 41.8 | No | — | BOAMP | Award notices carry DATE_ATTRIBUTION (95%); absent from DECP. |
| Winner identity | Partial | 37.0 | Yes | 95.5 | Both | BOAMP gives the name, DECP the SIRET; complementary. |
| Procedure type | Yes | 87.4 | Yes | 85.4 | Both | Structured in both sources. |
| Offers received | No | — | Partial | 26.4 | DECP | DECP-only field (filled on ~1/4 of rows); useful competition signal. |
| Notice type (AAPC/award) | Yes | 100.0 | No | — | BOAMP | Notice-level granularity (AAPC, award, rectif.) exists only in BOAMP. |
| Linked notices (renewal hints) | Partial | 46.2 | No | — | BOAMP | annonce_lie links award to original notice; key for Week 3. |

**Primary-source recommendation.** BOAMP should be the primary source for the internship corpus: it is the only source that covers the full 2015-2024 period, distinguishes contract notices from award notices (the event structure survival analysis needs), provides the richest free-text objects for NLP, and links award notices back to the original call (annonce_lie), which Week 3's renewal linking will build on. DECP (tabular decp.parquet) should be used as the enrichment source from 2019 onwards: joined on buyer SIRET/name + object/CPV similarity, it supplies the fields BOAMP lacks or fills poorly — mandatory buyer SIRET, SIRENE-normalized buyer name, amount, dureeMois and, crucially, the notification date that defines the survival-time origin. Its in-scope volume (3,039 digital PdL contracts, 2018-2024) already approaches the 2,000-5,000-contract corpus target on its own. The join is still non-trivial (BOAMP legacy notices carry no SIRET) and should be prototyped in Week 2.
