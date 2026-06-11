# BOAMP field profile (500-notice sample, PdL, 2015-2024)

| field | dtype | non_null | missing_pct | n_unique | sample_values | notes |
|---|---|---|---|---|---|---|
| idweb | object | 500 | 0.0 | 500 | 15-30947 ; 15-31397 ; 15-31464 ; 15-32296 | BOAMP notice identifier (YY-NNNNNN); unique key, always present. |
| dateparution | object | 500 | 0.0 | 318 | 2015-03-02 ; 2015-03-03 ; 2015-03-04 ; 2015-03-16 | Publication date on BOAMP; the only universally present date. |
| datefindiffusion | object | 500 | 0.0 | 378 | 2015-03-27 ; 2015-04-01 ; 2015-04-24 ; 2015-06-03 |  |
| datelimitereponse | object | 127 | 74.6 | 119 | 2015-03-27T11:30:00+00:00 ; 2015-04-24T15:00:00+00:00 ; 2015-04-17T11:00:00+00:00 ; 2015-04-14T11:00:00+00:00 | Offer deadline; only meaningful for contract notices. |
| nomacheteur | object | 500 | 0.0 | 183 | SMICTOM de la Vallée de l'Authion ; SDIS de la Sarthe ; Sdis de la Mayenne ; CHU de Nantes | Buyer name, free text; many spelling variants per buyer. |
| code_departement | object | 500 | 0.0 | 52 | 49 ; 72 ; 53 ; 44 | Department list ('\|'-joined); JOUE notices may list all 5 PdL departments. |
| famille | object | 500 | 0.0 | 2 | JOUE ; FNS | JOUE (EU threshold) vs FNS (national); drives form completeness. |
| nature | object | 500 | 0.0 | 5 | APPEL_OFFRE ; ATTRIBUTION ; RECTIFICATIF ; PRE-INFORMATION | APPEL_OFFRE / ATTRIBUTION / RECTIFICATIF…; structured code. |
| nature_libelle | object | 500 | 0.0 | 5 | Avis de marché ; Résultat de marché ; Rectificatif ; Avis informatif |  |
| type_procedure | object | 437 | 12.6 | 6 | OUVERT ; NEGOCIE ; PROCEDURE_ADAPTE ; RESTREINT | Structured procedure code (OUVERT, PROCEDURE_ADAPTE…). |
| type_marche | object | 450 | 10.0 | 4 | SERVICES ; FOURNITURES ; TRAVAUX ; SERVICES\|FOURNITURES |  |
| type_avis | object | 444 | 11.2 | 3 | 5\|1\| ; \|10\|6 ; 5\|\|3 |  |
| descripteur_libelle | object | 500 | 0.0 | 188 | Informatique (matériel)\|Location\|Logiciel\|Maintenance ; Logiciel ; Groupe électrogène\|Matériel électrique\|Matériel de secours e… ; Horodateur\|Matériel électrique | BOAMP in-house thesaurus, NOT CPV; well filled. |
| objet | object | 500 | 0.0 | 468 | Acquisition de systèmes d'identification embarqués, location… ; evolution du systeme de gestion operationnelle au profit du … ; fourniture de petits materiels d'incendie et de secours et p… ; fourniture de logiciels ibm-lotus et de prestations d'assist… | Free-text contract object; main NLP input for Phase 2. |
| titulaire | object | 185 | 63.0 | 178 | SIS ; ASI ; TRYADE ; DCS EASYWARE | Winning supplier name(s); award notices only. |
| annonce_lie | object | 231 | 53.8 | 231 | 14-175328 ; 14-163454 ; 14-175676 ; 14-154990 | Linked notice idwebs; key for AAPC<->award linking (Week 3). |
| contractfolderid | object | 40 | 92.0 | 37 | 074bcfdb-0518-4346-a1c3-86cd0d60a303 ; 1d202127-4262-44c9-91f4-aab10975833f ; 69d075a7-f7f6-4774-8c6b-a3c98703af61 ; bc75e13f-7dc9-4a63-8bad-e2becae9b42d |  |
| etat | object | 500 | 0.0 | 4 | INITIAL ; ANNULATION ; RECTIFICATIF ; MODIFICATION |  |
| url_avis | object | 500 | 0.0 | 500 | https://www.boamp.fr/pages/avis/?q=idweb:15-30947 ; https://www.boamp.fr/pages/avis/?q=idweb:15-31397 ; https://www.boamp.fr/pages/avis/?q=idweb:15-31464 ; https://www.boamp.fr/pages/avis/?q=idweb:15-32296 |  |
| donnees_format | object | 500 | 0.0 | 2 | legacy ; eforms | legacy (pre-2024 forms) vs eforms (EU UBL, 2024+). |
| cpv_principal | object | 489 | 2.2 | 197 | 48000000 ; 48814300 ; 48517000 ; 38720000 | Main CPV; structured code, see specificity deep-dive. |
| cpv_all | object | 500 | 0.0 | 278 | 48000000 ; 48814300 ; None\|35311400\|31121000\|34928410\|44423200\|43830000\|35111100\|4… ; 48517000 | Main + per-lot CPV codes ('\|'-joined). |
| buyer_siret | object | 40 | 92.0 | 15 | 443928874 ; 83095506800044 ; 21850047800209 ; 17440005100010 | Buyer SIRET; almost only present in eForms notices (2024+). |
| buyer_cp | object | 485 | 3.0 | 138 | 49250 ; 72190 ; 53005 ; 44093 |  |
| buyer_ville | object | 498 | 0.4 | 143 | Beaufort en vallee ; COULAINES ; Laval cedex ; Nantes |  |
| amount_eur | float64 | 223 | 55.4 | 176 | 150000.0 ; 230957.2 ; 187264.29 ; 93195.0 | Estimated or awarded amount; see deep-dive (0/ceiling values). |
| duration_months | float64 | 172 | 65.6 | 26 | 12.0 ; 36.0 ; 48.0 ; 24.0 | Declared duration normalized to months; see Task 5. |
| duration_source_field | object | 172 | 65.6 | 2 | DUREE_MOIS ; cbc:DurationMeasure | Original field the duration came from. |
| date_attribution | object | 209 | 58.2 | 188 | 2015-02-17 ; 2015-02-19 ; 2015-03-02 ; 2015-03-11 | Award date; award notices only, placeholder dates excluded. |
| date_publication_anterieure | object | 111 | 77.8 | 107 | 2014-11-21 ; 2014-10-30 ; 2014-10-25 ; 2014-06-28 | Publication date of the original contract notice, as recalled inside award notices. |
