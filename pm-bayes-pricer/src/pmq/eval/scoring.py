"""Grading probability forecasts.

A forecast of "70%" is neither right nor wrong on a single event, so we grade over many events
with a *proper scoring rule*: a score that is best, on average, only when you report your true
belief. That removes any incentive to exaggerate.

* **Log loss**: -ln(probability you gave to what actually happened). Confidently wrong is
  punished savagely (saying 1% and being wrong costs 4.6; saying 40% and being wrong costs 0.9).
* **Brier score**: squared gap between the forecast and the outcome (1 or 0). Gentler on
  confident misses, easy to read: 0 is perfect, 0.25 is what "always say 50%" earns.

Lower is better for both. A score on its own means little; it is only meaningful against a
baseline. Here the baseline is the market's own price, via the *skill score*.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize
from scipy.special import expit, logit

FloatArray = NDArray[np.float64]
EPS = 1e-6


def _pair(p: ArrayLike, y: ArrayLike) -> tuple[FloatArray, FloatArray]:
    prob = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    out = np.asarray(y, dtype=float)
    if prob.shape != out.shape:
        raise ValueError("forecasts and outcomes must have the same shape")
    return prob, out


def log_loss_each(p: ArrayLike, y: ArrayLike) -> FloatArray:
    prob, out = _pair(p, y)
    return np.asarray(-(out * np.log(prob) + (1 - out) * np.log(1 - prob)))


def brier_each(p: ArrayLike, y: ArrayLike) -> FloatArray:
    prob, out = _pair(p, y)
    return np.asarray((prob - out) ** 2)


def log_loss(p: ArrayLike, y: ArrayLike) -> float:
    return float(log_loss_each(p, y).mean())


def brier(p: ArrayLike, y: ArrayLike) -> float:
    return float(brier_each(p, y).mean())


def skill_score(score: float, baseline_score: float) -> float:
    """1 - score/baseline. Positive: beat the baseline. Zero: tied. Negative: worse."""
    return 1.0 - score / baseline_score


@dataclass(frozen=True)
class BrierDecomposition:
    """Brier = reliability - resolution + uncertainty (Murphy, 1973).

    * reliability: gap between stated probabilities and observed frequencies (lower = better).
    * resolution:  how much the forecasts separate easy events from hard ones (higher = better).
    * uncertainty: how unpredictable the events are to begin with; nobody controls this.
    """

    reliability: float
    resolution: float
    uncertainty: float


def brier_decomposition(p: ArrayLike, y: ArrayLike, bins: int = 10) -> BrierDecomposition:
    prob, out = _pair(p, y)
    base_rate = out.mean()
    edges = np.linspace(0, 1, bins + 1)
    which = np.clip(np.digitize(prob, edges[1:-1]), 0, bins - 1)
    rel = res = 0.0
    for b in range(bins):
        mask = which == b
        n = mask.sum()
        if n == 0:
            continue
        rel += n * (prob[mask].mean() - out[mask].mean()) ** 2
        res += n * (out[mask].mean() - base_rate) ** 2
    n_total = len(prob)
    return BrierDecomposition(rel / n_total, res / n_total, float(base_rate * (1 - base_rate)))


def reliability_table(p: ArrayLike, y: ArrayLike, bins: int = 10) -> list[dict[str, float]]:
    """Per probability bucket: average forecast, how often it happened, and how many forecasts.

    Perfect calibration means the first two match in every row: of all the times you said ~30%,
    it should have happened ~30% of the time.
    """
    prob, out = _pair(p, y)
    edges = np.linspace(0, 1, bins + 1)
    which = np.clip(np.digitize(prob, edges[1:-1]), 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = which == b
        if mask.any():
            rows.append(
                {
                    "bin": float(b),
                    "mean_forecast": float(prob[mask].mean()),
                    "frequency": float(out[mask].mean()),
                    "count": float(mask.sum()),
                }
            )
    return rows


def calibration_slope_intercept(p: ArrayLike, y: ArrayLike) -> tuple[float, float]:
    """Fit logit(P(happens)) = a + b * logit(forecast). Returns (intercept a, slope b).

    A calibrated forecaster has a = 0 and b = 1. A slope below 1 means the forecasts are
    over-confident (should be pulled toward 50%); above 1 means under-confident.
    """
    prob, out = _pair(p, y)
    x = logit(prob)

    def nll(theta: FloatArray) -> float:
        q = np.clip(expit(theta[0] + theta[1] * x), EPS, 1 - EPS)
        return float(-np.sum(out * np.log(q) + (1 - out) * np.log(1 - q)))

    fit = minimize(nll, x0=np.array([0.0, 1.0]), method="BFGS")
    return float(fit.x[0]), float(fit.x[1])


def paired_bootstrap_difference(
    loss_a: ArrayLike,
    loss_b: ArrayLike,
    n_resamples: int = 5000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """Is forecaster A really better than B, or did it get lucky on this sample?

    Takes the per-event losses of both forecasters on the *same* events, re-draws events with
    replacement thousands of times, and looks at the spread of (mean loss A - mean loss B).
    Returns (observed difference, lower, upper). If the interval straddles 0, the data cannot
    tell the two apart. Negative means A is better (lower loss).
    """
    a, b = np.asarray(loss_a, dtype=float), np.asarray(loss_b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("losses must cover the same events")
    diff = a - b
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_resamples, len(diff)))
    means = diff[idx].mean(axis=1)
    tail = (1 - level) / 2
    return float(diff.mean()), float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))


def cluster_bootstrap_difference(
    loss_a: ArrayLike,
    loss_b: ArrayLike,
    groups: ArrayLike,
    n_resamples: int = 4000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """Like ``paired_bootstrap_difference`` but resamples whole *groups* (e.g. calendar weeks).

    Contracts that overlap in time are not independent: two 7-day contracts opened an hour
    apart are almost the same bet. Resampling individual contracts would make the evidence look
    far stronger than it is. Resampling whole weeks keeps overlapping contracts together, so
    the interval honestly reflects how many *independent* stretches of history we have.
    """
    a, b = np.asarray(loss_a, dtype=float), np.asarray(loss_b, dtype=float)
    g = np.asarray(groups)
    diff = a - b
    _, inverse = np.unique(g, return_inverse=True)
    sums = np.bincount(inverse, weights=diff)
    counts = np.bincount(inverse).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, sums.size, size=(n_resamples, sums.size))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    tail = (1 - level) / 2
    return (
        float(diff.mean()),
        float(np.quantile(means, tail)),
        float(np.quantile(means, 1 - tail)),
    )
