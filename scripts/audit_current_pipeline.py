from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import nbformat
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from current_boamp_lib import ROOT, TABLES_AUDIT, RUN_LOG_DIR, append_run_log, ensure_dirs, utc_now

STALE_PATTERNS = [
    "study ends at " + "2024-12-31",
    "current result has " + "1,210 eligible contracts",
    "current result has " + "254 events",
    "current event rate is " + "21.0%",
    "old " + "665-event result is current",
    "M0 balanced is current selected " + "method",
    "event means legal " + "renewal",
]

REQUIRED_FILES = [
    "data/raw/boamp_current/download_metadata.json",
    "data/processed/boamp_current/boamp_full_flat.csv",
    "data/processed/boamp_current/boamp_full_clean_enriched.csv",
    "reports/tables/data/buyer_enrichment_summary.csv",
    "data/processed/boamp_current/boamp_survival_population_base.csv",
    "data/processed/boamp_current/boamp_candidate_pairs_enriched.csv",
    "reports/tables/linkage/method_comparison_current_dataset.csv",
    "reports/tables/linkage/final_selected_event_definition_current.csv",
    "reports/tables/validation/classifier_benchmark_current.csv",
    "reports/tables/survival/survival_summary_current.csv",
    "reports/tables/survival/live_contract_risk_scores_current.csv",
    "reports/current_boamp_recurrence_study_report.tex",
    "reports/current_boamp_recurrence_study_report.pdf",
    "reports/current_source_values_used.csv",
    "scripts/update_current_notebooks.py",
    "scripts/validate_current_notebooks.py",
    "scripts/mark_legacy_reports_superseded.py",
    "validation_robustness/validation_robustness_analysis.ipynb",
]


def classify_file(path: Path) -> dict:
    rel = str(path.relative_to(ROOT))
    if "/boamp_current/" in rel or rel.endswith("_current.csv") or "current_boamp" in rel or "current_source_values_used" in rel:
        role = "current dataset artifact"
        keep = "keep_use"
        reason = "Part of the current enriched dataset pipeline"
    elif rel.startswith("archive/"):
        role = "archive"
        keep = "archive"
        reason = "Historical archived artifact"
    elif any(token in rel for token in ["boamp_phase2_survival", "calibrated_balanced", "m2_balanced", "final_draft"]):
        role = "historical current-before-refresh output"
        keep = "archive"
        reason = "Older 2015-2024 outputs retained for Git/history, not current reporting"
    elif rel.startswith("scripts/") or rel.startswith("notebooks/") or rel.startswith("buyer_siren_enrichment/"):
        role = "pipeline code"
        keep = "keep_use"
        reason = "Code or notebook may still document reusable logic"
    elif rel.startswith("data/raw/boamp_full") or rel.startswith("data/raw/boamp_sample"):
        role = "historical raw BOAMP cache"
        keep = "archive"
        reason = "Older raw cache; current raw data lives under data/raw/boamp_current"
    else:
        role = "supporting project file"
        keep = "keep_use"
        reason = "No safe delete decision without deeper dependency analysis"
    return {"file_path": rel, "role": role, "keep_use_archive_delete": keep, "reason": reason, "notes": ""}


def stale_hits() -> list[str]:
    files = [
        ROOT / "README.md",
        ROOT / "boamp_renewal_linking_quality" / "README.md",
        ROOT / "validation_robustness" / "validation_robustness_report.md",
        *(ROOT / "reports").rglob("*.md"),
        *(ROOT / "reports").rglob("*.tex"),
    ]
    hits = []
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in STALE_PATTERNS:
            if pattern in text:
                hits.append(f"{path.relative_to(ROOT)}::{pattern}")
    notebooks = [
        *sorted((ROOT / "notebooks").glob("*.ipynb")),
        *sorted((ROOT / "boamp_renewal_linking_quality").glob("*.ipynb")),
        ROOT / "validation_robustness" / "validation_robustness_analysis.ipynb",
    ]
    for path in notebooks:
        if not path.exists():
            continue
        nb = nbformat.read(path, as_version=4)
        source = "\n".join(cell.source for cell in nb.cells if cell.cell_type in {"markdown", "code"})
        for pattern in STALE_PATTERNS:
            if pattern in source:
                hits.append(f"{path.relative_to(ROOT)}::{pattern}")
    return hits


def main() -> None:
    ensure_dirs()
    files = [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and ".venv" not in p.parts
        and "__pycache__" not in p.parts
    ]
    audit = pd.DataFrame([classify_file(p) for p in files])
    audit.to_csv(RUN_LOG_DIR / "current_project_file_audit.csv", index=False)

    rows = []
    for rel in REQUIRED_FILES:
        path = ROOT / rel
        rows.append({"check": rel, "status": "PASS" if path.exists() and path.stat().st_size > 0 else "FAIL", "detail": "exists" if path.exists() else "missing"})
    hits = stale_hits()
    rows.append({"check": "no_stale_old_values_remain", "status": "PASS" if not hits else "WARN", "detail": " | ".join(hits[:20])})
    rows.append({"check": "no_broken_required_paths", "status": "PASS" if all((ROOT / rel).exists() for rel in REQUIRED_FILES) else "FAIL", "detail": "required current outputs checked"})
    try:
        subprocess.run([sys.executable, "-m", "compileall", "scripts", "buyer_siren_enrichment", "validation_robustness", "event_validation"], cwd=ROOT, check=True, capture_output=True, text=True)
        rows.append({"check": "compileall", "status": "PASS", "detail": "Python files compile"})
    except subprocess.CalledProcessError as exc:
        rows.append({"check": "compileall", "status": "FAIL", "detail": (exc.stdout + exc.stderr)[-1000:]})
    try:
        subprocess.run([sys.executable, "scripts/validate_current_notebooks.py"], cwd=ROOT, check=True, capture_output=True, text=True)
        rows.append({"check": "current_notebooks_validate", "status": "PASS", "detail": "Current notebooks execute through data/table cells"})
    except subprocess.CalledProcessError as exc:
        rows.append({"check": "current_notebooks_validate", "status": "FAIL", "detail": (exc.stdout + exc.stderr)[-1000:]})
    final = pd.DataFrame(rows)
    final.to_csv(TABLES_AUDIT / "final_current_pipeline_audit.csv", index=False)
    append_run_log(
        [
            "",
            f"## Final current pipeline audit - {utc_now()}",
            f"- Required checks passed: {int(final['status'].eq('PASS').sum())}/{len(final)}",
            f"- Warnings/failures: {final[~final['status'].eq('PASS')].to_dict('records')}",
        ]
    )
    print("=== Final current pipeline audit ===")
    print(final.to_string(index=False))


if __name__ == "__main__":
    main()
