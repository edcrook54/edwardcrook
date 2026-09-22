"""Volatility measurements that are safe to use at a given moment (no peeking at the future).

Every array here is indexed by an **anchor** hour ``i``: the moment a forecaster stands at,
about to start hour ``i``. Each value uses only hours ``< i``. That single rule is what stops
look-ahead bias, and ``tests/test_no_lookahead.py`` enforces it by changing the future and
checking these numbers do not move.

Units: ``*_var`` arrays are variance per **day**; ``*_vol`` arrays are annualised volatility.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import lfilter

from pmq.crypto.bayes_vol import VarianceBelief, filter_discounted
from pmq.crypto.grid import HOURS_PER_YEAR, HourlyGrid

FloatArray = NDArray[np.float64]


def _sum_before(x: FloatArray, window: int) -> FloatArray:
    """out[i] = sum of x[i - window : i]; NaN until a full window exists."""
    c = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(x.size, np.nan)
    i = np.arange(window, x.size)
    out[i] = c[i] - c[i - window]
    return out


def _state_before(y: FloatArray) -> FloatArray:
    """Shift a filtered series so that out[i] is the state after hour i-1."""
    out = np.full(y.size, np.nan)
    out[1:] = y[:-1]
    return out


@dataclass(frozen=True)
class VolFeatures:
    log_ret: FloatArray  # hourly log returns (return of hour h is ln(close[h]/close[h-1]))
    trailing30_vol: FloatArray  # std of hourly returns over 30 days, annualised
    rv1d_var: FloatArray  # average daily realised variance over the last 1 / 7 / 30 days
    rv7d_var: FloatArray
    rv30d_var: FloatArray
    ewma_vol: FloatArray
    bayes_alpha: FloatArray  # discounted inverse-gamma state (per-hour variance belief)
    bayes_beta: FloatArray
    coverage30: FloatArray  # share of the last 30 days' hours in which trades happened


def hourly_log_returns(grid: HourlyGrid) -> FloatArray:
    r = np.zeros(len(grid))
    r[1:] = np.diff(np.log(grid.close))
    return r


def build_features(
    grid: HourlyGrid, ewma_half_life_days: float = 5.0, bayes_memory_days: float = 10.0
) -> VolFeatures:
    r = hourly_log_returns(grid)
    w30 = 30 * 24

    s1 = _sum_before(r, w30)
    s2 = _sum_before(r**2, w30)
    var_h = (s2 - s1**2 / w30) / (w30 - 1)
    trailing = np.sqrt(np.maximum(var_h, 0.0) * HOURS_PER_YEAR)

    rv1 = _sum_before(grid.rv, 24)
    rv7 = _sum_before(grid.rv, 7 * 24) / 7.0
    rv30 = _sum_before(grid.rv, w30) / 30.0

    lam = 0.5 ** (1.0 / (ewma_half_life_days * 24.0))
    ewma_var_h = lfilter([1.0 - lam], [1.0, -lam], r**2)
    ewma_vol = np.sqrt(_state_before(ewma_var_h) * HOURS_PER_YEAR)

    delta = 1.0 - 1.0 / (bayes_memory_days * 24.0)
    seed_belief = VarianceBelief.from_annual_vol(0.6, HOURS_PER_YEAR, strength=2.0)
    alpha, beta = filter_discounted(r, delta, seed_belief)

    coverage = _sum_before(grid.traded.astype(float), w30) / w30
    return VolFeatures(
        log_ret=r,
        trailing30_vol=trailing,
        rv1d_var=rv1,
        rv7d_var=rv7,
        rv30d_var=rv30,
        ewma_vol=ewma_vol,
        bayes_alpha=_state_before(alpha),
        bayes_beta=_state_before(beta),
        coverage30=coverage,
    )
