"""Performance metrics — vendored from
`crypto-cointegration-signal/src/evaluation/metrics.py` (see
`backtest.py`'s module docstring for why vendoring, not importing, shared
utilities is the deliberate choice in this repo). Only the asset-agnostic
pieces this project needs are ported.
"""

from __future__ import annotations

import numpy as np


def sharpe_ratio(returns: np.ndarray, periods_per_year: int) -> float:
    returns = np.asarray(returns, dtype=float)
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    return float(np.mean(returns) / np.std(returns) * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: np.ndarray) -> float:
    equity_curve = np.asarray(equity_curve, dtype=float)
    if len(equity_curve) == 0:
        return 0.0
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = equity_curve - running_max
    return float(drawdown.min())
