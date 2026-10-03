"""Single-asset directional backtest from an LLM sentiment score.

`WalkForwardSplitter` is a verbatim vendor of
`crypto-cointegration-signal/src/backtest/engine.py`'s class of the same
name. `crypto-cointegration-signal`'s `BacktestEngine` and `CostModel`
don't fit here, for two different reasons: `BacktestEngine` is
pairs-trading-specific (two assets, a hedge ratio), and `CostModel`'s
turnover-based cost (`np.diff(positions)`) assumes a *continuously-sampled*
position series, where a flat `[1, 1]` means one position held open across
both steps. That's wrong for this project's data: each row is an
independent bet at one FOMC meeting, and consecutive meetings are >=41 days
apart (far longer than any horizon tested) - two consecutive same-sign
signals are two separate round-trip trades, not one continuously-held
position, and a turnover-diff would have charged the second one close to
nothing. This was caught by this project's own audit (see AUDIT.md) when a
first draft vendored `CostModel` for this use directly. The fix is the flat
per-event round-trip cost in `run_backtest` below, not a shared vendor.
"""

from __future__ import annotations

import numpy as np


class WalkForwardSplitter:
    """Chronological train/test split - no shuffling, test window strictly
    after train.
    """

    def __init__(self, oos_fraction: float):
        self.oos_fraction = oos_fraction

    def split(self, n_obs: int) -> tuple[slice, slice]:
        split_idx = int(round(n_obs * (1 - self.oos_fraction)))
        return slice(0, split_idx), slice(split_idx, n_obs)


def positions_from_scores(scores: np.ndarray, threshold: float) -> np.ndarray:
    """+1 above `threshold`, -1 below `-threshold`, flat otherwise.

    `scores` are the LLM's hawkish(+)/dovish(-) score for each event; the
    position is taken at the event itself, to be paired with a forward
    return computed strictly *after* that event's timestamp (see
    `returns/bars.py`) - no look-ahead as long as the caller holds that
    contract.
    """
    scores = np.asarray(scores, dtype=float)
    positions = np.zeros_like(scores)
    positions[scores >= threshold] = 1.0
    positions[scores <= -threshold] = -1.0
    return positions


def run_backtest(
    scores: np.ndarray, forward_returns: np.ndarray, cost_bps: float, threshold: float
) -> dict[str, np.ndarray]:
    positions = positions_from_scores(scores, threshold)
    gross_returns = positions * np.asarray(forward_returns, dtype=float)
    # Entry + exit cost for every independent bet (see module docstring for
    # why this isn't a turnover-diff over the position series).
    round_trip_cost = 2.0 * (cost_bps / 1e4)
    costs = np.where(positions != 0, round_trip_cost, 0.0)
    net_returns = gross_returns - costs
    equity_curve = np.cumprod(1 + net_returns) - 1
    return {
        "positions": positions,
        "gross_returns": gross_returns,
        "net_returns": net_returns,
        "equity_curve": equity_curve,
    }
