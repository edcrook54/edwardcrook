"""Shared chart styling and data loading for the notebooks (kept out of the way of the prose)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from pmq.ingest import kalshi, polymarket
from pmq.pricing.clean import mid_price

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# Categorical slots 1-3 of a palette validated for colour-blind separation. Text never wears
# a series colour; the coloured mark beside a label carries identity.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GREY, INK, INK_SOFT, GRID, SURFACE = "#9a9a94", "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def setup() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK_SOFT,
            "axes.titlecolor": INK,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "xtick.color": INK_SOFT,
            "ytick.color": INK_SOFT,
            "text.color": INK,
            "lines.linewidth": 2,
            "legend.frameon": False,
            "legend.labelcolor": INK_SOFT,
            "font.size": 10,
            "figure.figsize": (7.5, 3.8),
            "figure.dpi": 110,
        }
    )


def label_point(ax, x, y, text, dx=0.0, dy=0.0, ha="left") -> None:  # type: ignore[no-untyped-def]
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha,
                fontsize=9, color=INK_SOFT)


def load_fomc() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Recorded quotes for the October 2026 FOMC meeting from both venues."""
    now = datetime(2026, 9, 20, tzinfo=UTC)
    poly_event = json.loads((FIXTURES / "polymarket_fomc_oct_event.json").read_text())[0]
    kal_event = json.loads((FIXTURES / "kalshi_kxfed_oct_events.json").read_text())["events"][0]

    pm, ps = polymarket.parse_event(poly_event, now)
    km, ks = kalshi.parse_event(kal_event, now)

    def frame(markets, snaps, key):  # type: ignore[no-untyped-def]
        by_id = {s.market_id: s for s in snaps}
        rows = []
        for m in markets:
            s = by_id[m.market_id]
            rows.append(
                {
                    key: m.bucket_bps if key == "bps" else m.strike_pct,
                    "label": m.outcome_label,
                    "bid": s.best_bid,
                    "ask": s.best_ask,
                    "last": s.last_price,
                    "mid": mid_price(s.best_bid, s.best_ask, s.last_price),
                }
            )
        return pd.DataFrame(rows).sort_values(key).reset_index(drop=True)

    poly = frame(pm, ps, "bps")
    kal = frame(km, ks, "strike")
    rules = {
        "polymarket": (pm[0].resolution_rule or "").split("\n")[0],
        "kalshi": km[0].resolution_rule or "",
    }
    return poly, kal, rules


def load_price_history() -> pd.Series:
    payload = json.loads((FIXTURES / "polymarket_prices_history.json").read_text())
    snaps = polymarket.parse_price_history(payload, "polymarket:history")
    return pd.Series({s.ts: s.last_price for s in snaps}, name="price").sort_index()
