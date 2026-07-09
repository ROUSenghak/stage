from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

PALETTE = [
    "#4C78A8",
    "#72B7B2",
    "#F58518",
    "#54A24B",
    "#B279A2",
    "#E45756",
    "#8D6B94",
]


def apply_academic_style() -> None:
    sns.set_theme(context="paper", style="whitegrid", palette=PALETTE)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "grid.linewidth": 0.6,
            "legend.frameon": False,
            "figure.dpi": 130,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def save_pdf_png(fig, path_without_suffix: str | Path) -> None:
    path = Path(path_without_suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".pdf"))
    fig.savefig(path.with_suffix(".png"), dpi=300)
