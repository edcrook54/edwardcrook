"""First-passage ("will it touch the level?") probabilities for a geometric Brownian motion.

Plain-English version. A contract asks: *will the price touch $K at any moment before time T?*
That is a question about the price's **highest point** (for a level above today's price) or
**lowest point** (below), not about where it ends up. Traders know it as a "one-touch" option.

The model behind every formula here is the standard one: the log-price does a random walk with
a small drift and a volatility ``sigma``. Time is measured in years (crypto trades 24/7, so
365 days), volatility is annualised, and ``mu`` is the *price* drift per year (0 = the price is
a martingale). The log-price drift is then ``nu = mu - sigma**2 / 2``.

Derivation sketch (the reflection principle). For a driftless random walk, every path that
touches the barrier and ends *below* it can be mirrored (after the touch) into a path that ends
*above* it. So paths that touch = paths that end above + their mirror images that end below,
which gives  P(touch) = 2 * P(end above)  when the log-price has no drift. With drift the
mirror argument gets a correction factor, and the answer is

    P(touch) = Phi((-b + nu T) / s) + exp(2 nu b / sigma^2) * Phi((-b - nu T) / s)

with ``s = sigma * sqrt(T)``, ``b = ln(K / S0)`` the log distance to the barrier, and Phi the
standard normal CDF.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq
from scipy.special import log_ndtr, ndtr

FloatArray = NDArray[np.float64]

# Broadie-Glasserman-Kou constant: -zeta(1/2) / sqrt(2 pi). See ``touch_probability``.
BGK_BETA = 0.5826
MINUTE_YEARS = 1.0 / (365.0 * 24.0 * 60.0)


def _b(s0: FloatArray, k: FloatArray, sign: FloatArray) -> FloatArray:
    """Log distance to the barrier, measured in the direction we need to travel (>= 0)."""
    return np.asarray(sign * np.log(k / s0), dtype=float)


def touch_probability(
    s0: ArrayLike,
    k: ArrayLike,
    sigma: ArrayLike,
    t_years: ArrayLike,
    mu: ArrayLike = 0.0,
    monitor_dt_years: float = 0.0,
    direction: Literal["auto", "up", "down"] = "auto",
) -> FloatArray:
    """Probability that the price touches ``k`` at some point in the next ``t_years``.

    * ``direction="auto"``: an up-barrier if ``k > s0``, a down-barrier if ``k < s0``.
    * If the barrier is already crossed (``k == s0`` or on the near side) the answer is 1.
    * ``monitor_dt_years``: real venues do not watch the price continuously; they check
      1-minute candle highs and lows. A discretely watched barrier is *harder* to hit than a
      continuously watched one. Broadie, Glasserman and Kou (1997) showed the effect is almost
      exactly the same as pushing the barrier away by ``exp(0.5826 * sigma * sqrt(dt))``, so we
      apply that shift. Pass ``MINUTE_YEARS`` for 1-minute monitoring, 0 for continuous.

    All arguments broadcast, so whole grids of contracts can be priced in one call.
    """
    s, kk, sg, t, m = (
        np.asarray(x, dtype=float) for x in np.broadcast_arrays(s0, k, sigma, t_years, mu)
    )
    if np.any(s <= 0) | np.any(kk <= 0) | np.any(sg <= 0) | np.any(t < 0):
        raise ValueError("s0, k, sigma must be positive and t_years non-negative")
    if direction == "auto":
        sign = np.where(kk >= s, 1.0, -1.0)
    else:
        sign = np.full_like(s, 1.0 if direction == "up" else -1.0)

    b = _b(s, kk, sign) + BGK_BETA * sg * np.sqrt(monitor_dt_years)
    nu = sign * (m - 0.5 * sg**2)  # drift measured in the direction of the barrier
    root_t = sg * np.sqrt(t)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        d1 = (-b + nu * t) / root_t
        d2 = (-b - nu * t) / root_t
        # exp(a) * Phi(x) evaluated in log-space so that large drifts cannot overflow.
        reflected = np.exp(2.0 * nu * b / sg**2 + log_ndtr(d2))
        prob = ndtr(d1) + reflected
    prob = np.where(t <= 0, 0.0, prob)
    prob = np.where(_b(s, kk, sign) <= 0, 1.0, prob)
    return np.asarray(np.clip(prob, 0.0, 1.0), dtype=float)


def terminal_probability(
    s0: ArrayLike,
    k: ArrayLike,
    sigma: ArrayLike,
    t_years: ArrayLike,
    mu: ArrayLike = 0.0,
    above: bool = True,
) -> FloatArray:
    """Probability the price is above (or below) ``k`` at the *end* of the window.

    This is the "digital" answer, ignoring where the price wandered on the way. Compare with
    ``touch_probability``: for far-from-the-money levels the touch is about twice as likely.
    """
    s, kk, sg, t, m = (
        np.asarray(x, dtype=float) for x in np.broadcast_arrays(s0, k, sigma, t_years, mu)
    )
    d = (np.log(s / kk) + (m - 0.5 * sg**2) * t) / (sg * np.sqrt(t))
    p_above = ndtr(d)
    return np.asarray(p_above if above else 1.0 - p_above, dtype=float)


def first_exit_upper_probability(
    s0: float, lower: float, upper: float, sigma: float, mu: float = 0.0
) -> float:
    """Probability of touching ``upper`` before ``lower`` (no time limit): "X or Y first" markets.

    Gambler's-ruin argument: find a function of the price that is a fair game (a *scale
    function*); the exit probability is where the start sits between the two barriers *on that
    scale*. With log-price drift nu and variance sigma^2, the scale function is
    s(x) = 1 - exp(-2 nu x / sigma^2) (or simply x when nu = 0), with x = ln(price).
    """
    if not lower < s0 < upper:
        raise ValueError("need lower < s0 < upper")
    nu = mu - 0.5 * sigma**2
    x, lo, hi = np.log(s0), np.log(lower), np.log(upper)
    if abs(nu) < 1e-12:
        return float((x - lo) / (hi - lo))

    def scale(y: float) -> float:
        return float(1.0 - np.exp(-2.0 * nu * y / sigma**2))

    return float((scale(x) - scale(lo)) / (scale(hi) - scale(lo)))


def implied_volatility(
    price: float,
    s0: float,
    k: float,
    t_years: float,
    mu: float = 0.0,
    monitor_dt_years: float = 0.0,
    bounds: tuple[float, float] = (0.01, 20.0),
) -> float:
    """The volatility that makes the model reproduce a market's touch price (NaN if impossible).

    This turns a prediction-market price into the same unit traders quote options in. Read
    a whole ladder of strikes this way and you get the market's *volatility smile*: high implied
    vol for far-out strikes means the crowd expects fatter tails than a plain GBM.
    """
    lo, hi = bounds

    def gap(sig: float) -> float:
        return float(touch_probability(s0, k, sig, t_years, mu, monitor_dt_years)) - price

    if not (gap(lo) <= 0.0 <= gap(hi)):
        return float("nan")
    return float(brentq(gap, lo, hi, xtol=1e-10))
