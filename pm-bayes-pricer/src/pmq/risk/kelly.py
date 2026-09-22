"""How much of your bankroll to stake on an edge (the Kelly criterion).

Plain-English version. You believe an event has probability p, and the market sells a Yes
contract for c dollars (pays $1 if it happens). Your edge is p - c. If you stake too little you
waste the edge; too much and a run of bad luck ruins you. Kelly's answer is the stake that
maximises the long-run growth rate of your bankroll, i.e. the average of ln(wealth):

    stake fraction f* = (p - c) / (1 - c)             (buy Yes when p > c)

Example: you think 60%, the price is 50 cents, so f* = 0.10 / 0.50 = 20% of your bankroll.

Two honest caveats that shape how it is used here:

1. **Kelly assumes p is exactly right.** Real model probabilities are noisy, so people bet a
   fixed fraction of Kelly (half-Kelly is common). The maths below shows why this is cheap
   insurance: it gives up little growth but cuts the odds of a deep drawdown massively.
2. **Uncertainty about p does not, by itself, shrink a single bet.** Expected log-growth is a
   straight line in p, so a bet sized on the *average* of your uncertain p is already the
   best one. What protects you from an over-confident model is pooling it toward the market
   (``pmq.models.pooling``) and calibrating it, not extra shrinkage inside Kelly.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import Bounds, LinearConstraint, minimize

FloatArray = NDArray[np.float64]


def kelly_fraction(p: float, price: float) -> float:
    """Signed Kelly stake: positive = buy Yes at ``price``, negative = buy No, 0 = no bet.

    Buying No costs (1 - price) and wins with probability (1 - p), which by the same algebra
    gives a stake of (price - p) / price.
    """
    if not (0.0 < price < 1.0):
        raise ValueError("price must be strictly between 0 and 1")
    if p > price:
        return (p - price) / (1.0 - price)
    if p < price:
        return -(price - p) / price
    return 0.0


def expected_log_growth(f: float, p: float, price: float) -> float:
    """Average per-bet growth of ln(wealth) from staking fraction ``f`` on Yes at ``price``."""
    if not 0.0 <= f < 1.0:
        raise ValueError("stake fraction must be in [0, 1)")
    win = 1.0 + f * (1.0 - price) / price
    return float(p * np.log(win) + (1.0 - p) * np.log(1.0 - f))


def drawdown_probability(kelly_multiple: float, drawdown_fraction: float) -> float:
    """Chance your bankroll *ever* falls to ``drawdown_fraction`` of its running peak.

    Standard continuous-time approximation: with a stake of ``kelly_multiple`` x Kelly,
    P(ever drop to x of peak) = x ** (2 / kelly_multiple - 1). Full Kelly (1.0) has a 50%
    chance of ever halving; half-Kelly (0.5) only 12.5%. An approximation, not a guarantee.
    """
    if not (0.0 < drawdown_fraction < 1.0) or kelly_multiple <= 0:
        raise ValueError("need 0 < drawdown_fraction < 1 and a positive Kelly multiple")
    if kelly_multiple >= 2.0:
        return 1.0  # over-betting twice Kelly has negative growth: ruin is certain in the limit
    return float(drawdown_fraction ** (2.0 / kelly_multiple - 1.0))


def kelly_mutually_exclusive(probs: Sequence[float], prices: Sequence[float]) -> FloatArray:
    """Best stakes when spreading a bankroll across Yes contracts on mutually exclusive outcomes.

    Exactly one outcome happens. If outcome j happens, wealth becomes
        1 - sum(f) + f_j / price_j
    (you lose everything staked on the other outcomes and collect on contract j). We maximise
    the probability-weighted average of ln(wealth) over the stakes f >= 0 with sum(f) <= 1.
    The problem is concave, so a standard solver finds the global answer.
    """
    p, c = np.asarray(probs, dtype=float), np.asarray(prices, dtype=float)
    if p.shape != c.shape or not np.isclose(p.sum(), 1.0):
        raise ValueError("need matching probs (adding to 1) and prices")

    def neg_growth(f: FloatArray) -> float:
        wealth = 1.0 - f.sum() + f / c
        return float(-np.sum(p * np.log(np.maximum(wealth, 1e-12))))

    start = np.zeros_like(p)
    result = minimize(
        neg_growth,
        start,
        method="SLSQP",
        bounds=Bounds(0.0, 0.999),
        constraints=LinearConstraint(np.ones((1, len(p))), -np.inf, 0.999),
    )
    return np.asarray(np.clip(result.x, 0.0, None), dtype=float)
