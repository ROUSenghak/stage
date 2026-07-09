# Enriched Current BOAMP Dataset Run Log

- Branch: `boamp_enriched_current_dataset`
- Starting commit: `4847230b1024f49e1a41f8d34e7967acd6688c21`
- Execution date: 2026-07-09
- Scope: Pays de la Loire digital BOAMP notices for the Gigalis internship corpus
- Objective: build a new current enriched dataset, rerun linkage and survival analysis, and make current outputs internally consistent
- Interpretation guardrail: events are proxy recurrences, not legally verified renewals

## Initial environment

- Main Python environment: `.venv/bin/python3`
- Missing methodology packages installed before execution: `recordlinkage`, `xgboost`, `datasketch`
- Old 2015-2024 outputs are preserved as historical artifacts and are not used as current comparison tables.

## BOAMP current download - 2026-07-09T13:45:53+00:00
- Requested range: 2015-01-01 to 2026-07-09
- Retained notices: 3656
- Actual range: {'min_date': '2015-03-02', 'max_date': '2026-07-09'}
- Duplicate count: 0
- Errors: none

## Current clean/enrichment - 2026-07-09T13:50:28+00:00
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_full_clean_enriched.csv
- Records: 3656
- APPEL_OFFRE: 2216
- Buyer key types: {'SIREN_ENRICHED': 2246, 'NAME': 930, 'SIRET': 480}

## Current analytical population - 2026-07-09T13:50:36+00:00
- Study end/censoring date: 2026-07-09
- APPEL_OFFRE rows: 2215
- Eligible for linkage: 1661
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_survival_population_base.csv

## Current candidate generation - 2026-07-09T13:50:52+00:00
- Eligible sources: 1661
- Candidate pairs: 7699
- Text backend: tfidf_char_3_5_fallback
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_candidate_pairs_enriched.csv

## Current candidate generation - 2026-07-09T13:51:37+00:00
- Eligible sources: 1661
- Candidate pairs: 7699
- Text backend: sentence_transformers:paraphrase-multilingual-MiniLM-L12-v2
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_candidate_pairs_enriched.csv

## Current linkage methods - 2026-07-09T13:51:55+00:00
- Eligible contracts: 1661
- Selected method: M0 balanced
- Event count: 183
- Event rate: 0.1102
- Limitation: real BOAMP precision/recall are not directly observed.

## Current methodology tests - 2026-07-09T13:56:32+00:00
- Candidate pairs tested: 7699
- Synthetic/silver positives: 70
- Real BOAMP precision/recall not claimed.

## Current survival analysis - 2026-07-09T13:56:42+00:00
- Selected method: M0 balanced
- Eligible contracts: 1661
- Events: 183
- Event rate: 0.1102
- Selected AFT model: LogLogisticAFT

## Current live scoring - 2026-07-09T13:56:48+00:00
- Prediction date: 2026-07-09
- Live contracts: 1661
- Expected 12-month recurrences: 48.44

## Current report/source trace - 2026-07-09T13:56:56+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Current report/source trace - 2026-07-09T13:57:18+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Final current pipeline audit - 2026-07-09T13:58:16+00:00
- Required checks passed: 17/17
- Warnings/failures: []

## Current survival analysis - 2026-07-09T13:59:04+00:00
- Selected method: M0 balanced
- Eligible contracts: 1661
- Events: 183
- Event rate: 0.1102
- Selected AFT model: LogLogisticAFT

## Current live scoring - 2026-07-09T13:59:12+00:00
- Prediction date: 2026-07-09
- Live contracts: 1661
- Expected 12-month recurrences: 48.44

## Current report/source trace - 2026-07-09T13:59:12+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Final current pipeline audit - 2026-07-09T13:59:30+00:00
- Required checks passed: 17/17
- Warnings/failures: []

## Current linkage methods - 2026-07-09T13:59:59+00:00
- Eligible contracts: 1661
- Selected method: M0 balanced
- Event count: 183
- Event rate: 0.1102
- Limitation: real BOAMP precision/recall are not directly observed.

## Current methodology tests - 2026-07-09T14:02:20+00:00
- Candidate pairs tested: 7699
- Synthetic/silver positives: 70
- Real BOAMP precision/recall not claimed.

## Current live scoring - 2026-07-09T14:02:26+00:00
- Prediction date: 2026-07-09
- Live contracts: 1661
- Expected 12-month recurrences: 48.44

## Current survival analysis - 2026-07-09T14:02:30+00:00
- Selected method: M0 balanced
- Eligible contracts: 1661
- Events: 183
- Event rate: 0.1102
- Selected AFT model: LogLogisticAFT

## Current report/source trace - 2026-07-09T14:02:38+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Current live scoring - 2026-07-09T14:03:17+00:00
- Prediction date: 2026-07-09
- Live contracts: 1661
- Expected 12-month recurrences: 48.44

## Current report/source trace - 2026-07-09T14:03:17+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Final current pipeline audit - 2026-07-09T14:03:43+00:00
- Required checks passed: 17/17
- Warnings/failures: []

## Legacy report supersession - 2026-07-09T14:11:27+00:00
- Rewrote active-facing historical report files as explicit superseded wrappers.
- Files updated: 17
  - reports/calibrated_event_definition_summary.md
  - reports/phase1_data_quality_report.md
  - reports/report_consistency_audit.md
  - reports/method_comparison_report_consistency_audit_20260708.md
  - reports/audit/report_consistency_findings.md
  - reports/audit/statistical_explanation_improvements.md
  - reports/week1_summary.md
  - reports/final_draft/README.md
  - boamp_renewal_linking_quality/README.md
  - validation_robustness/validation_robustness_report.md
  - reports/datasets_documentation.tex
  - reports/phase1_technical_report.tex
  - reports/internship_report.tex
  - reports/data_quality_report/data_quality_report.tex
  - reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
  - reports/audit/current_results_audit.csv
  - reports/final_draft/source_values_used.csv

## Final current pipeline audit - 2026-07-09T14:12:17+00:00
- Required checks passed: 22/22
- Warnings/failures: []

## Legacy report supersession - 2026-07-09T14:13:22+00:00
- Rewrote active-facing historical report files as explicit superseded wrappers.
- Files updated: 17
  - reports/calibrated_event_definition_summary.md
  - reports/phase1_data_quality_report.md
  - reports/report_consistency_audit.md
  - reports/method_comparison_report_consistency_audit_20260708.md
  - reports/audit/report_consistency_findings.md
  - reports/audit/statistical_explanation_improvements.md
  - reports/week1_summary.md
  - reports/final_draft/README.md
  - boamp_renewal_linking_quality/README.md
  - validation_robustness/validation_robustness_report.md
  - reports/datasets_documentation.tex
  - reports/phase1_technical_report.tex
  - reports/internship_report.tex
  - reports/data_quality_report/data_quality_report.tex
  - reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
  - reports/audit/current_results_audit.csv
  - reports/final_draft/source_values_used.csv

## Final current pipeline audit - 2026-07-09T14:14:01+00:00
- Required checks passed: 22/22
- Warnings/failures: []

## Final current pipeline audit - 2026-07-09T14:14:31+00:00
- Required checks passed: 22/22
- Warnings/failures: []

## BOAMP current download - 2026-07-09T14:24:21+00:00
- Requested range: 2015-01-01 to 2026-07-09
- Retained notices: 3656
- Actual range: {'min_date': '2015-03-02', 'max_date': '2026-07-09'}
- Duplicate count: 0
- Errors: none

## Current clean/enrichment - 2026-07-09T14:24:29+00:00
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_full_clean_enriched.csv
- Records: 3656
- APPEL_OFFRE: 2216
- Buyer key types: {'SIREN_ENRICHED': 2246, 'NAME': 930, 'SIRET': 480}

## Current analytical population - 2026-07-09T14:24:37+00:00
- Study end/censoring date: 2026-07-09
- APPEL_OFFRE rows: 2215
- Eligible for linkage: 1661
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_survival_population_base.csv

## Current candidate generation - 2026-07-09T14:25:00+00:00
- Eligible sources: 1661
- Candidate pairs: 7699
- Text backend: tfidf_char_3_5_fallback
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_candidate_pairs_enriched.csv

## Current candidate generation - 2026-07-09T14:25:39+00:00
- Eligible sources: 1661
- Candidate pairs: 7699
- Text backend: sentence_transformers:paraphrase-multilingual-MiniLM-L12-v2
- Output: /home/senghakrou/stage-1/data/processed/boamp_current/boamp_candidate_pairs_enriched.csv

## Current linkage methods - 2026-07-09T14:25:58+00:00
- Eligible contracts: 1661
- Selected method: M0 balanced
- Event count: 183
- Event rate: 0.1102
- Limitation: real BOAMP precision/recall are not directly observed.

## Current methodology tests - 2026-07-09T14:28:27+00:00
- Candidate pairs tested: 7699
- Synthetic/silver positives: 70
- Real BOAMP precision/recall not claimed.

## Current survival analysis - 2026-07-09T14:28:35+00:00
- Selected method: M0 balanced
- Eligible contracts: 1661
- Events: 183
- Event rate: 0.1102
- Selected AFT model: LogLogisticAFT

## Current live scoring - 2026-07-09T14:28:40+00:00
- Prediction date: 2026-07-09
- Live contracts: 1661
- Expected 12-month recurrences: 48.44

## Current report/source trace - 2026-07-09T14:28:45+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Legacy report supersession - 2026-07-09T14:28:56+00:00
- Rewrote active-facing historical report files as explicit superseded wrappers.
- Files updated: 17
  - reports/calibrated_event_definition_summary.md
  - reports/phase1_data_quality_report.md
  - reports/report_consistency_audit.md
  - reports/method_comparison_report_consistency_audit_20260708.md
  - reports/audit/report_consistency_findings.md
  - reports/audit/statistical_explanation_improvements.md
  - reports/week1_summary.md
  - reports/final_draft/README.md
  - boamp_renewal_linking_quality/README.md
  - validation_robustness/validation_robustness_report.md
  - reports/datasets_documentation.tex
  - reports/phase1_technical_report.tex
  - reports/internship_report.tex
  - reports/data_quality_report/data_quality_report.tex
  - reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
  - reports/audit/current_results_audit.csv
  - reports/final_draft/source_values_used.csv

## Final current pipeline audit - 2026-07-09T14:29:20+00:00
- Required checks passed: 22/22
- Warnings/failures: []

## Current report/source trace - 2026-07-09T14:30:15+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Current report/source trace - 2026-07-09T14:30:34+00:00
- Report: /home/senghakrou/stage-1/reports/current_boamp_recurrence_study_report.tex
- Source trace: reports/current_source_values_used.csv

## Legacy report supersession - 2026-07-09T14:30:41+00:00
- Rewrote active-facing historical report files as explicit superseded wrappers.
- Files updated: 17
  - reports/calibrated_event_definition_summary.md
  - reports/phase1_data_quality_report.md
  - reports/report_consistency_audit.md
  - reports/method_comparison_report_consistency_audit_20260708.md
  - reports/audit/report_consistency_findings.md
  - reports/audit/statistical_explanation_improvements.md
  - reports/week1_summary.md
  - reports/final_draft/README.md
  - boamp_renewal_linking_quality/README.md
  - validation_robustness/validation_robustness_report.md
  - reports/datasets_documentation.tex
  - reports/phase1_technical_report.tex
  - reports/internship_report.tex
  - reports/data_quality_report/data_quality_report.tex
  - reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
  - reports/audit/current_results_audit.csv
  - reports/final_draft/source_values_used.csv

## Final current pipeline audit - 2026-07-09T14:31:03+00:00
- Required checks passed: 22/22
- Warnings/failures: []

## Rich current report rebuild - 2026-07-09T14:46:47+00:00
- Replaced shortened wrapper-style final report with a rich current synthesis.
- Wrote reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
- Wrote reports/current_boamp_recurrence_study_report.tex
- Updated current and final_draft source traces.

## Rich current report rebuild - 2026-07-09T14:48:43+00:00
- Replaced shortened wrapper-style final report with a rich current synthesis.
- Wrote reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
- Wrote reports/current_boamp_recurrence_study_report.tex
- Wrote reports/phase1_technical_report.tex
- Wrote reports/internship_report.tex
- Updated current and final_draft source traces.

## Rich current report rebuild - 2026-07-09T14:49:11+00:00
- Replaced shortened wrapper-style final report with a rich current synthesis.
- Wrote reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
- Wrote reports/current_boamp_recurrence_study_report.tex
- Wrote reports/phase1_technical_report.tex
- Wrote reports/internship_report.tex
- Updated current and final_draft source traces.

## Final current pipeline audit - 2026-07-09T14:49:50+00:00
- Required checks passed: 22/22
- Warnings/failures: []

## Rich current report rebuild - 2026-07-09T14:50:19+00:00
- Replaced shortened wrapper-style final report with a rich current synthesis.
- Wrote reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
- Wrote reports/current_boamp_recurrence_study_report.tex
- Wrote reports/phase1_technical_report.tex
- Wrote reports/internship_report.tex
- Wrote reports/datasets_documentation.tex
- Wrote reports/data_quality_report/data_quality_report.tex
- Updated current and final_draft source traces.

## Final current pipeline audit - 2026-07-09T14:50:49+00:00
- Required checks passed: 22/22
- Warnings/failures: []
