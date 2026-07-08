# Gigalis BOAMP Proxy Recurrence Survival Report

This folder contains a first draft synthesis report for the BOAMP / Gigalis internship project.

## Main files

- `gigalis_boamp_proxy_recurrence_survival_report.tex`: LaTeX source.
- `gigalis_boamp_proxy_recurrence_survival_report.pdf`: rendered report.
- `source_values_used.csv`: trace table for reported numbers.
- `figures/`: generated diagrams plus selected current project figures copied for this draft.

## Current selected method

The selected main method is **M2 balanced** with match-probability threshold `0.65`. The final modeling input is:

`data/processed/boamp_phase2_survival_method_m2_balanced.csv`

It contains 1,210 eligible contracts, 254 proxy recurrence events, and 956 censored rows (21.0% event rate).

## Historical results

`data/processed/boamp_phase2_survival.csv` is retained as the historical pre-calibration baseline only. It has 665 events out of 1,210 eligible contracts (55.0%).

M0 balanced remains the conservative transparent baseline, with 269 proxy events (22.2%).

## Rebuild

From the repository root:

```bash
python3 reports/final_draft/build_final_draft.py
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error reports/final_draft/gigalis_boamp_proxy_recurrence_survival_report.tex
```

The build script reads only executed project outputs already present in the repository. It does not rerun notebooks.

## Important interpretation

The event variable is a proxy recurrence outcome: an identifiable reappearance of a similar procurement need. It is not a verified legal renewal, and real BOAMP precision/recall are not directly observable.
