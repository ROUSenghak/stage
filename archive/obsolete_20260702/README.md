# Archive — obsolete files moved 2026-07-02

Files moved here during the 2026-07-02 project audit/cleanup. Nothing in this
folder is used by the current pipeline, notebooks, or reports. Kept for
traceability instead of permanent deletion.

| File | Origin | Reason archived |
|---|---|---|
| `reports/internship_report_before_consistency_fix.{tex,pdf}` | `reports/` | Pre-2026-06-23 snapshot; superseded by current `reports/internship_report.tex` |
| `reports/internship_report_before_restructure.tex` | `reports/` | Pre-2026-06-25 snapshot; superseded |
| `reports/phase1_technical_report_before_consistency_fix.{tex,pdf}` | `reports/` | Pre-2026-06-23 snapshot; superseded |
| `reports/phase1_technical_report_before_restructure.tex` | `reports/` | Pre-2026-06-25 snapshot; superseded |
| `reports/data_quality_report_before_restructure.tex` | `reports/data_quality_report/` | Pre-2026-06-25 snapshot; superseded |
| `root_build/internship_report_root_copy.pdf` | repo root | Stale duplicate PDF built 2026-06-29 at the root; canonical PDF is `reports/internship_report.pdf` |
| `root_build/phase1_technical_report_root_copy.pdf` | repo root | Stale duplicate PDF built 2026-06-29 at the root; canonical PDF is `reports/phase1_technical_report.pdf` |
| `data/boamp_full_clean_sirene.csv` | `data/processed/` | Legacy output of the deprecated `scripts/task_sirene_enrichment.py` step; superseded by `data/processed/boamp_full_clean_siren_enriched.csv` |
| `event_validation/boamp_event_validation_audit_W12_sample.xlsx` | `event_validation/outputs/` | Audit workbook whose sample was drawn from the obsolete W=12 / 1,100-contract dataset (contains 17 partial hand labels); superseded by the W=6 rebuild |
| `event_validation/manual_validation_sample_W12.csv` | `event_validation/outputs/` | Sample CSV drawn from the obsolete W=12 dataset |

Also deleted outright (untracked build artifacts, all gitignored):
root-level `internship_report.{aux,fdb_latexmk,fls,log,out}`,
`phase1_technical_report.{aux,fdb_latexmk,fls,log,out,toc}`, `__pycache__/` dirs.

Kept despite looking deprecated:
- `scripts/task_sirene_enrichment.py` — still imported by
  `buyer_siren_enrichment/step2_api_enrich.py` (API helper functions).
- `scripts/task1_boamp_fetch.py` and `data/processed/boamp_sample_flat.csv` —
  explicitly kept for reference per `README.md`.
- `reports/report_consistency_audit.md`, `reports/audit/*` — historical audit
  records (their numbers describe past states by design).
