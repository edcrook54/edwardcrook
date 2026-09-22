"""Estimating and forecasting volatility from price bars.

Everything in the barrier formulas hinges on one number, the volatility ``sigma``, and it is
never observed directly: it has to be estimated from prices. Different estimators use different
slices of the data, so they differ in *efficiency* (how noisy the estimate is) and *bias*.

Conventions: prices come as NumPy arrays of bars; results are **annualised** volatilities
(standard deviations, not variances) unless the name says ``variance``. ``periods_per_year`` is
how many bars fit in a year; crypto trades 24/7 so 1-minute bars give 525,600.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
LN2 = math.log(2.0)


def _arr(x: ArrayLike) -> FloatArray:
    return np.asarray(x, dtype=float)


def log_returns(close: ArrayLike) -> FloatArray:
    c = _arr(close)
    return np.asarray(np.diff(np.log(c)), dtype=float)


def close_to_close(close: ArrayLike, periods_per_year: float) -> float:
    """Standard deviation of log returns between closing prices. Simple, and the benchmark."""
    r = log_returns(close)
    return float(np.std(r, ddof=1) * math.sqrt(periods_per_year))


def parkinson(high: ArrayLike, low: ArrayLike, periods_per_year: float) -> float:
    """Uses each bar's high-low range: sigma^2 = mean( ln(H/L)^2 ) / (4 ln 2).

    Roughly 5x more statistically efficient than close-to-close on the same bars because the
    range carries information about the whole path, not just its endpoints. Assumes no drift
    and no jumps, and is slightly biased *low* when bars are sampled discretely.
    """
    h, l = _arr(high), _arr(low)  # noqa: E741
    var = np.mean(np.log(h / l) ** 2) / (4.0 * LN2)
    return float(math.sqrt(var * periods_per_year))


def garman_klass(
    open_: ArrayLike, high: ArrayLike, low: ArrayLike, close: ArrayLike, periods_per_year: float
) -> float:
    """Adds the open-to-close move to the range: 0.5 ln(H/L)^2 - (2 ln 2 - 1) ln(C/O)^2."""
    o, h, l, c = _arr(open_), _arr(high), _arr(low), _arr(close)  # noqa: E741
    var = np.mean(0.5 * np.log(h / l) ** 2 - (2.0 * LN2 - 1.0) * np.log(c / o) ** 2)
    return float(math.sqrt(max(var, 0.0) * periods_per_year))


def rogers_satchell(
    open_: ArrayLike, high: ArrayLike, low: ArrayLike, close: ArrayLike, periods_per_year: float
) -> float:
    """ln(H/C) ln(H/O) + ln(L/C) ln(L/O): stays unbiased even when the price trends."""
    o, h, l, c = _arr(open_), _arr(high), _arr(low), _arr(close)  # noqa: E741
    var = np.mean(np.log(h / c) * np.log(h / o) + np.log(l / c) * np.log(l / o))
    return float(math.sqrt(max(var, 0.0) * periods_per_year))


def realized_variance(returns: ArrayLike) -> float:
    """Sum of squared high-frequency returns over the window (a variance, not annualised)."""
    return float(np.sum(_arr(returns) ** 2))


def bipower_variation(returns: ArrayLike) -> float:
    """(pi/2) * sum |r_i| |r_{i-1}|: a variance estimate that jumps barely affect.

    A jump makes one return huge, which blows up realised variance. In bipower variation each
    huge return is multiplied by a *neighbouring ordinary* return, so a lone jump adds little.
    """
    r = np.abs(_arr(returns))
    return float((math.pi / 2.0) * np.sum(r[1:] * r[:-1]))


def jump_share(returns: ArrayLike) -> float:
    """Fraction of realised variance attributable to jumps: max(0, (RV - BV) / RV)."""
    rv = realized_variance(returns)
    return 0.0 if rv <= 0 else max(0.0, (rv - bipower_variation(returns)) / rv)


def ewma_variance(returns: ArrayLike, lam: float = 0.94) -> float:
    """Exponentially weighted variance (RiskMetrics): recent returns count more.

    ``lam`` is the memory: 0.94 on daily data means each day's weight is 94% of the day before.
    Returns the per-period variance (not annualised).
    """
    r = _arr(returns)
    if r.size == 0:
        raise ValueError("no returns")
    w = lam ** np.arange(r.size - 1, -1, -1)
    return float(np.sum(w * r**2) / np.sum(w))


def qlike(proxy_variance: ArrayLike, forecast_variance: ArrayLike) -> float:
    """Loss for grading variance forecasts: mean( p/f - ln(p/f) - 1 ). Zero when perfect.

    "QLIKE" is preferred over squared error because it stays reliable when the thing being
    forecast is a noisy proxy of true variance, and it does not let a handful of huge-variance
    days dominate the score.
    """
    p, f = _arr(proxy_variance), _arr(forecast_variance)
    ratio = p / f
    return float(np.mean(ratio - np.log(ratio) - 1.0))


def signature_plot(
    close_1m: ArrayLike, multiples: tuple[int, ...] = (1, 2, 5, 10, 30, 60)
) -> dict[int, float]:
    """Annualised realised vol when prices are sampled every ``m`` minutes.

    If prices were a clean random walk the answer would not depend on ``m``. Rising volatility
    at very fine sampling reveals *microstructure noise* (bid-ask bounce): the tiny moves are
    partly fake. The point where the curve flattens is a sensible sampling interval.
    """
    c = _arr(close_1m)
    out: dict[int, float] = {}
    for m in multiples:
        sub = c[::m]
        r = np.diff(np.log(sub))
        out[m] = float(math.sqrt(np.sum(r**2) / (len(r) * m) * 525_600))
    return out


class HarRV:
    """HAR-RV forecast of average daily variance over the next ``horizon_days`` (Corsi, 2009).

    Volatility is persistent over several time scales at once: what happened yesterday, this
    week and this month all help predict tomorrow. HAR fits one linear regression, here **in
    logs** because variance is heavily right-skewed:

        ln(next-h-day mean RV) = c + b_d ln(RV_today) + b_w ln(mean RV, 5d) + b_m ln(mean RV, 22d)

    Fitting in levels lets a few explosive days (Bitcoin 2017-18) dominate the coefficients and
    the model then over-forecasts calmer years by 2x. In logs the leftover error is close to
    log-normal with standard deviation ``resid_std``: an honest measure of forecast uncertainty.
    """

    FLOOR = 1e-12

    def __init__(self, horizon_days: int = 1) -> None:
        self.horizon = horizon_days
        self.coef: FloatArray | None = None
        self.resid_std: float = float("nan")

    @classmethod
    def _features(cls, rv: FloatArray) -> FloatArray:
        n = len(rv)
        csum = np.concatenate([[0.0], np.cumsum(rv)])
        idx = np.arange(21, n)
        d = np.log(np.maximum(rv[idx], cls.FLOOR))
        w = np.log(np.maximum((csum[idx + 1] - csum[idx - 4]) / 5.0, cls.FLOOR))
        m = np.log(np.maximum((csum[idx + 1] - csum[idx - 21]) / 22.0, cls.FLOOR))
        return np.column_stack([np.ones(len(idx)), d, w, m])

    def fit(self, daily_rv: ArrayLike) -> HarRV:
        rv = _arr(daily_rv)
        x = self._features(rv)  # row j describes "today" = day j + 21
        h = self.horizon
        csum = np.concatenate([[0.0], np.cumsum(rv)])
        idx = np.arange(21, len(rv))
        keep = idx + h <= len(rv) - 1  # the h days after "today" must exist
        target = np.log(np.maximum((csum[idx[keep] + 1 + h] - csum[idx[keep] + 1]) / h, self.FLOOR))
        self.coef, *_ = np.linalg.lstsq(x[keep], target, rcond=None)
        self.resid_std = float(np.std(target - x[keep] @ self.coef))
        return self

    def predict_log(self, daily_rv: ArrayLike) -> float:
        """Median forecast, as a log-variance, from data up to today."""
        if self.coef is None:
            raise RuntimeError("fit first")
        return float(self._features(_arr(daily_rv))[-1] @ self.coef)

    def predict(self, daily_rv: ArrayLike) -> float:
        """Mean forecast of average daily variance (median times the log-normal correction)."""
        return float(math.exp(self.predict_log(daily_rv) + 0.5 * self.resid_std**2))
