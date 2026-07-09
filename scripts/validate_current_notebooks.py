from __future__ import annotations

from pathlib import Path

import matplotlib
import nbformat

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]


NOTEBOOKS = [
    *sorted((ROOT / "notebooks").glob("*.ipynb")),
    *sorted((ROOT / "boamp_renewal_linking_quality").glob("*.ipynb")),
    ROOT / "validation_robustness" / "validation_robustness_analysis.ipynb",
]


def main() -> None:
    failures: list[tuple[str, int, str]] = []
    for path in NOTEBOOKS:
        nb = nbformat.read(path, as_version=4)
        namespace = {"__name__": "__main__"}
        print(f"VALIDATING {path.relative_to(ROOT)}")
        for index, cell in enumerate(nb.cells):
            if cell.cell_type != "code":
                continue
            source = cell.source
            if "from IPython.display import Image" in source:
                print(f"  skip display-only cell {index}")
                continue
            try:
                exec(compile(source, f"{path}:cell{index}", "exec"), namespace)
            except Exception as exc:
                failures.append((str(path.relative_to(ROOT)), index, repr(exc)))
                print(f"  FAIL cell {index}: {exc}")
                break
        else:
            print("  OK")
    if failures:
        print("\nNotebook validation failures:")
        for item in failures:
            print(item)
        raise SystemExit(1)
    print("\nAll current notebooks validated.")


if __name__ == "__main__":
    main()
