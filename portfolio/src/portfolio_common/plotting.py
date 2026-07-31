"""Consistent plotting theme shared across every project in the portfolio.

Import and call `set_style()` at the top of a notebook so every chart —
GARCH vol plots, BMA-SDF pricing-error bars, credit-risk ROC curves —
looks like it came from the same person.
"""
from __future__ import annotations

import matplotlib.pyplot as plt

PALETTE = {
    "primary": "#1F3B57",
    "accent": "#C9A24B",
    "positive": "#2E7D32",
    "negative": "#B23B3B",
    "grid": "#E5E5E5",
}


def set_style() -> None:
    """Apply the shared portfolio matplotlib style."""
    plt.rcParams.update(
        {
            "figure.figsize": (9, 5),
            "figure.dpi": 110,
            "axes.grid": True,
            "grid.color": PALETTE["grid"],
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "font.size": 10,
            "legend.frameon": False,
            "axes.prop_cycle": plt.cycler(
                color=[PALETTE["primary"], PALETTE["accent"], PALETTE["positive"], PALETTE["negative"]]
            ),
        }
    )
