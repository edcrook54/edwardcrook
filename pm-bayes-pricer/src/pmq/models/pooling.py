"""Combining several probability forecasts into one.

Plain-English version. We have two opinions on the same question: the market's price and our
model's forecast. Averaging the probabilities directly is the obvious move but has a flaw:
it can never be *more* confident than the most confident input. If two independent sources both
say 90%, the sensible combined view is above 90%.

The fix is to average in *log-odds* space instead (a "logarithmic opinion pool"). Log-odds
stretch probabilities so that 90% -> 99% is as big a step as 50% -> 90%, which is how evidence
actually accumulates. Each source gets a weight: how much we trust it.

For a weight w on the model and (1 - w) on the market, the pooled probability is

    logit(p) = w * logit(model) + (1 - w) * logit(market)          logit(x) = ln( x / (1 - x) )

w = 0 means "just trust the market" and w = 1 means "just trust the model". We choose w from
history by asking which value would have scored best (lowest log loss).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit

FloatArray = NDArray[np.float64]
EPS = 1e-6


def _clip(p: ArrayLike) -> FloatArray:
    return np.asarray(np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS), dtype=float)


def pool_binary(model: ArrayLike, market: ArrayLike, weight_on_model: float) -> FloatArray:
    """Log-odds blend of two yes/no forecasts."""
    if not 0.0 <= weight_on_model <= 1.0:
        raise ValueError("weight must be between 0 and 1")
    z = weight_on_model * logit(_clip(model)) + (1 - weight_on_model) * logit(_clip(market))
    return np.asarray(expit(z), dtype=float)


def pool_categorical(sources: ArrayLike, weights: ArrayLike) -> FloatArray:
    """Log pool for a full outcome distribution.

    ``sources`` has shape (n_sources, n_outcomes), each row a probability vector. The pooled
    forecast is proportional to prod_s( p_s[k] ** w_s ), re-normalised so it adds to 1.
    """
    p = _clip(sources)
    w = np.asarray(weights, dtype=float)
    if p.ndim != 2 or w.shape != (p.shape[0],) or not np.isclose(w.sum(), 1.0):
        raise ValueError("need one weight per source, adding to 1")
    log_pool = w @ np.log(p)
    log_pool -= log_pool.max()
    pooled = np.exp(log_pool)
    return np.asarray(pooled / pooled.sum(), dtype=float)


def fit_weight_on_model(
    model: ArrayLike, market: ArrayLike, outcomes: ArrayLike
) -> tuple[float, float]:
    """Best weight on the model, judged by log loss on past resolved contracts.

    Returns (weight, log_loss_at_weight). A weight of ~0 is an honest finding: it says the
    market already contains everything the model knows.
    """
    y = np.asarray(outcomes, dtype=float)

    def loss(w: float) -> float:
        p = pool_binary(model, market, w)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    result = minimize_scalar(loss, bounds=(0.0, 1.0), method="bounded")
    return float(result.x), float(result.fun)
