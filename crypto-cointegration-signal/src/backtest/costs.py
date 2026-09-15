"""
Transaction cost modelling.

Keep this honest: use a realistic estimate of Kraken taker fees + slippage
for the pair's typical trade size, not a token cost that flatters the
backtest. cost_bps in config.yaml is a placeholder - replace it with a
sourced number before reporting any results.
"""

import numpy as np


class CostModel:
    """Deducts a flat per-side cost (in bps of notional) whenever a position
    changes - i.e. on entries, exits, and flips. A flip (long -> short or vice
    versa) crosses two units of notional and is charged 2x.
    """

    def __init__(self, cost_bps: float):
        self.cost_bps = cost_bps

    def apply(self, gross_returns: np.ndarray, positions: np.ndarray) -> np.ndarray:
        turnover = np.abs(np.diff(positions, prepend=0.0))
        cost = turnover * (self.cost_bps / 1e4)
        return gross_returns - cost


def apply_costs(gross_returns: np.ndarray, positions: np.ndarray, cost_bps: float) -> np.ndarray:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return CostModel(cost_bps).apply(gross_returns, positions)
