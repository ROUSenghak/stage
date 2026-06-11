# DECP renewal linking report (prototype)

- Contracts analyzed: 3039
- Linked renewals (events): 252
- Linking rate: 8.29%
- Median observed duration (all): 30.95 months
- Median observed duration (events only): 33.78 months

## Matching rules
1. Same buyer (`acheteur_id`) and same CPV division (`codeCPV[:2]`).
2. Candidate appears later in time (`dateNotification`).
3. Time window around declared duration (`dureeMois ± 6 months`).
4. Object similarity >= 0.30 (token Jaccard).

## Notes
- This is a reproducible baseline for Week 3, not the final production linker.
- Next iteration should evaluate precision/recall on a manually reviewed sample and test stricter segmenting (CPV4) and one-to-one matching constraints.
