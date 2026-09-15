"""
Backtest engine for the cointegration spread signal.

Signal: z-score of the (Kalman-filtered) spread, with entry/exit
thresholds. Must be:
  1. cost-adjusted (see costs.py), and
  2. walk-forward validated - fit/calibrate on a train window, test on
     the following out-of-sample window, not the same data used to tune it.
"""

import numpy as np

from src.backtest.costs import CostModel


class ZScoreSignalGenerator:
    """Turns a rolling z-score of the spread into a long/short/flat position
    array, using hysteresis: enter at |z| >= entry_z, hold until |z| falls
    back below exit_z, then go flat. This avoids churning positions every
    time the z-score wobbles near the entry threshold.

    The calendar-grid alignment (src/data/alignment.py) backward-fills each
    asset's dollar bars, so a rolling window can be almost entirely flat
    (many duplicated grid rows) with only floating-point-scale variation
    left in it. Dividing by that near-zero rolling std blows the z-score up
    to nonsense magnitudes, so a window's std is compared against a floor
    set from the spread's *expanding* (all data strictly before t, never
    including t or later) variability and treated as uninformative (z=0)
    below that floor - a numerical stability guard, not a change to the
    underlying signal logic.

    This floor must be expanding rather than computed once from the full
    series: a one-shot `std(spread)` over the whole array leaks future
    variability into every decision, including ones made near the start of
    the series - concretely, calling this on a train+test-concatenated
    array (as the walk-forward evaluation does, so the Kalman filter and
    rolling z-score run as one continuous causal pass) would let the
    floor for an early, in-sample bar be partly set by test-period
    volatility, silently changing in-sample decisions depending on how
    much future data happens to be appended to the array.
    """

    def __init__(self, lookback: int, entry_z: float, exit_z: float, degenerate_atol: float = 1e-3):
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.degenerate_atol = degenerate_atol

    def zscore(self, spread: np.ndarray) -> np.ndarray:
        spread = np.asarray(spread, dtype=float)
        n = len(spread)
        z = np.full(n, np.nan)
        cumsum = np.cumsum(spread)
        cumsum_sq = np.cumsum(spread**2)
        for t in range(self.lookback, n):
            window = spread[t - self.lookback : t]
            mu, sigma = window.mean(), window.std()
            expanding_mean = cumsum[t - 1] / t
            expanding_var = max(cumsum_sq[t - 1] / t - expanding_mean**2, 0.0)
            floor = self.degenerate_atol * max(np.sqrt(expanding_var), 1e-12)
            z[t] = (spread[t] - mu) / sigma if sigma > floor else 0.0
        return z

    def positions(self, spread: np.ndarray) -> np.ndarray:
        z = self.zscore(spread)
        n = len(z)
        pos = np.zeros(n)
        state = 0.0
        for t in range(n):
            if np.isnan(z[t]):
                pos[t] = 0.0
                continue
            if state == 0.0:
                if z[t] >= self.entry_z:
                    state = -1.0  # spread rich -> short spread
                elif z[t] <= -self.entry_z:
                    state = 1.0  # spread cheap -> long spread
            elif abs(z[t]) <= self.exit_z:
                state = 0.0
            pos[t] = state
        return pos


class WalkForwardSplitter:
    """Chronological train/test split - no shuffling, test window strictly
    after train. Everything (window choice, hedge ratio, thresholds) must be
    calibrated on train only.
    """

    def __init__(self, oos_fraction: float):
        self.oos_fraction = oos_fraction

    def split(self, n_obs: int) -> tuple[slice, slice]:
        split_idx = int(round(n_obs * (1 - self.oos_fraction)))
        return slice(0, split_idx), slice(split_idx, n_obs)


class BacktestEngine:
    """Runs the cost-adjusted spread backtest given positions, per-asset PRICE
    levels, and a time-varying hedge ratio.

    A spread position of 1 unit A / hedge_ratio units B has a dollar P&L of
    (price_a[t] - price_a[t-1]) - hedge_ratio[t-1] * (price_b[t] - price_b[t-1]).
    That dollar P&L is normalised by the gross notional of the position,
    price_a[t-1] + hedge_ratio[t-1] * price_b[t-1], to get a genuine
    percentage return - dividing by hedge_ratio-weighted *log returns*
    directly (without this normalisation) produces returns scaled by
    whatever units the hedge ratio happens to be in, which is not
    interpretable as a percentage and inflates Sharpe/drawdown figures.
    The hedge ratio and position used at t are both the ones known at
    t-1, to avoid look-ahead.
    """

    def __init__(self, cost_model: CostModel):
        self.cost_model = cost_model

    def run(
        self,
        positions: np.ndarray,
        price_a: np.ndarray,
        price_b: np.ndarray,
        hedge_ratio: np.ndarray,
    ) -> dict:
        positions = np.asarray(positions, dtype=float)
        price_a = np.asarray(price_a, dtype=float)
        price_b = np.asarray(price_b, dtype=float)
        hedge_ratio = np.asarray(hedge_ratio, dtype=float)

        hedge_ratio_lag = np.roll(hedge_ratio, 1)
        hedge_ratio_lag[0] = hedge_ratio[0]

        dollar_pnl = np.diff(price_a, prepend=price_a[0]) - hedge_ratio_lag * np.diff(
            price_b, prepend=price_b[0]
        )
        gross_notional = price_a + hedge_ratio_lag * price_b
        gross_notional_lag = np.roll(gross_notional, 1)
        gross_notional_lag[0] = gross_notional[0]

        spread_returns = dollar_pnl / gross_notional_lag

        positions_lag = np.roll(positions, 1)
        positions_lag[0] = 0.0

        gross_returns = positions_lag * spread_returns
        gross_returns = np.nan_to_num(gross_returns)

        net_returns = self.cost_model.apply(gross_returns, positions_lag)
        equity_curve = np.cumprod(1 + net_returns) - 1

        return {
            "positions": positions_lag,
            "gross_returns": gross_returns,
            "net_returns": net_returns,
            "equity_curve": equity_curve,
        }


def zscore_signal(
    spread: np.ndarray, lookback: int, entry_z: float, exit_z: float
) -> np.ndarray:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return ZScoreSignalGenerator(lookback, entry_z, exit_z).positions(spread)


def run_backtest(
    positions: np.ndarray,
    price_a: np.ndarray,
    price_b: np.ndarray,
    hedge_ratio: np.ndarray,
    cost_bps: float,
) -> dict:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return BacktestEngine(CostModel(cost_bps)).run(positions, price_a, price_b, hedge_ratio)


def walk_forward_split(n_obs: int, oos_fraction: float) -> tuple[slice, slice]:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return WalkForwardSplitter(oos_fraction).split(n_obs)
