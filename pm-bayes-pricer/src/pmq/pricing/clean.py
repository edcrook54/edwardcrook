"""Turning quoted prices into probabilities.

A prediction-market contract pays $1 if the event happens, so a price of $0.40 is the market's
40% probability - *if* the price is fair. Two things get in the way:

1. Which number is "the price"? The last trade can be hours old. The middle of the bid and ask
   is usually a better estimate of where the market thinks fair value is.
2. In a market with several mutually exclusive outcomes, the Yes prices should add to $1.00
   (exactly one outcome happens). They usually add to a bit more. The excess is called the
   *overround* (or vig): the cushion the market keeps for itself. To get probabilities that
   add to 100% we have to decide who "owns" the excess. Three standard answers are below.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq

FloatArray = NDArray[np.float64]


def mid_price(
    bid: float | None,
    ask: float | None,
    last: float | None,
    max_spread: float = 0.10,
) -> float | None:
    """Best single-number estimate of the market's probability.

    * Both sides quoted and tight (spread <= ``max_spread``): the midpoint.
    * Otherwise: the last traded price, because a very wide quote says little.
    * Nothing available: None.
    """
    if bid is not None and ask is not None and ask - bid <= max_spread:
        return (bid + ask) / 2
    return last


def overround(prices: ArrayLike) -> float:
    """How far the Yes prices overshoot 100%. 0.03 means they add to 103%."""
    return float(np.sum(np.asarray(prices, dtype=float)) - 1.0)


def _validated(prices: ArrayLike) -> FloatArray:
    q = np.asarray(prices, dtype=float)
    if q.ndim != 1 or q.size < 2:
        raise ValueError("need a 1-D vector of at least two outcome prices")
    if np.any(q < 0) or np.any(q > 1):
        raise ValueError("prices must lie in [0, 1]")
    if q.sum() <= 0:
        raise ValueError("prices must not all be zero")
    return q


def normalise_proportional(prices: ArrayLike) -> FloatArray:
    """Divide every price by the total: p_i = q_i / sum(q).

    Simple and transparent, but it shaves the same *percentage* off every outcome, so it
    treats a 2% longshot and a 60% favourite as equally over-priced.
    """
    q = _validated(prices)
    return q / q.sum()


def normalise_power(prices: ArrayLike) -> FloatArray:
    """Raise every price to a power k so that they add to 1: sum(q_i ** k) = 1.

    Because prices are below 1, a bigger k shrinks small prices proportionally more than big
    ones. This puts more of the correction on longshots, matching the well-documented
    favourite-longshot bias (longshots are over-bet).
    """
    q = _validated(prices)
    if np.isclose(q.sum(), 1.0):
        return q / q.sum()
    positive = q > 0

    def excess(k: float) -> float:
        return float(np.sum(q[positive] ** k) - 1.0)

    k = brentq(excess, 1e-3, 200.0)
    out = np.zeros_like(q)
    out[positive] = q[positive] ** k
    return out


def normalise_shin(prices: ArrayLike) -> FloatArray:
    """Shin's method: assume a fraction ``z`` of the money comes from insiders who know the answer.

    Market makers widen prices to protect themselves from those insiders. Shin's model solves
    for the insider share ``z`` that explains the overround, then backs out the probabilities:

        p_i = ( sqrt(z^2 + 4 (1 - z) q_i^2 / S) - z ) / ( 2 (1 - z) ),   S = sum(q)

    ``z`` is found so that the p_i add to exactly 1. Like the power method it removes more from
    longshots than favourites, but it has an economic story attached.
    """
    q = _validated(prices)
    total = q.sum()
    if total <= 1.0:
        return q / total  # no overround to explain

    def p_of(z: float) -> FloatArray:
        return (np.sqrt(z**2 + 4 * (1 - z) * q**2 / total) - z) / (2 * (1 - z))

    z = brentq(lambda z: float(p_of(z).sum() - 1.0), 0.0, 1 - 1e-9)
    return p_of(z)


def insider_share(prices: ArrayLike) -> float:
    """The fitted Shin ``z``: a rough gauge of how 'informed' the market thinks its flow is."""
    q = _validated(prices)
    total = q.sum()
    if total <= 1.0:
        return 0.0

    def p_sum(z: float) -> float:
        p = (np.sqrt(z**2 + 4 * (1 - z) * q**2 / total) - z) / (2 * (1 - z))
        return float(p.sum() - 1.0)

    return float(brentq(p_sum, 0.0, 1 - 1e-9))
