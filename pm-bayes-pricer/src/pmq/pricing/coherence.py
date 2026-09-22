"""Making a set of related prices logically consistent, and translating between market layouts.

Kalshi quotes a *ladder*: "will the rate end above 3.75%? above 4.00%? above 4.25%?". Polymarket
quotes *buckets*: "cut 25", "no change", "hike 25". They describe the same uncertainty, so we
need to convert one into the other before comparing.

Ladders must obey one rule: a higher bar is harder to clear, so P(above 4.25%) can never exceed
P(above 4.00%). Real quotes sometimes break this (stale or thin markets). Buckets made by
subtracting neighbouring rungs would then have *negative probabilities*, so we first repair the
ladder with the smallest possible adjustment (isotonic regression).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
STEP_PCT = 0.25  # the Fed moves its target range in quarter-point steps


def isotonic_decreasing(values: ArrayLike, weights: ArrayLike | None = None) -> FloatArray:
    """Closest non-increasing sequence to ``values`` (least squares), by pool-adjacent-violators.

    Walk left to right. Whenever a value is *higher* than the one before it (a violation),
    replace both by their average, and keep merging backwards until the sequence is
    non-increasing. Weights let a well-traded rung resist being moved more than a thin one.
    """
    y = np.asarray(values, dtype=float)
    w = np.ones_like(y) if weights is None else np.asarray(weights, dtype=float)
    # Blocks of (weighted mean, total weight, count). Solve the increasing problem on -y.
    means: list[float] = []
    wts: list[float] = []
    counts: list[int] = []
    for value, weight in zip(-y, w, strict=True):
        means.append(float(value))
        wts.append(float(weight))
        counts.append(1)
        while len(means) > 1 and means[-2] > means[-1]:
            total = wts[-2] + wts[-1]
            means[-2] = (means[-2] * wts[-2] + means[-1] * wts[-1]) / total
            wts[-2] = total
            counts[-2] += counts[-1]
            means.pop()
            wts.pop()
            counts.pop()
    fitted = np.repeat(means, counts)
    return np.asarray(np.clip(-fitted, 0.0, 1.0), dtype=float)


def ladder_violations(p_above: ArrayLike) -> int:
    """Number of adjacent rungs where a higher bar is priced above a lower one."""
    p = np.asarray(p_above, dtype=float)
    return int(np.sum(np.diff(p) > 1e-12))


def _rung(ladder: dict[float, float], strike: float) -> float:
    for k, v in ladder.items():
        if abs(k - strike) < 1e-9:
            return v
    raise KeyError(f"ladder has no rung at {strike:.2f}%")


def ladder_to_buckets(
    ladder: dict[float, float],
    current_upper_pct: float,
    bucket_bps: tuple[int, ...] = (-50, -25, 0, 25, 50),
) -> dict[int, float]:
    """Convert "P(rate ends above X)" rungs into bucket probabilities.

    Let S(x) = P(new upper bound > x). The Fed moves in 0.25-point steps, so

        P(new bound == x)   = S(x - 0.25) - S(x)
        P(new bound <= x)   = 1 - S(x)         (bottom bucket, e.g. "cut 50 or more")
        P(new bound >= x)   = S(x - 0.25)      (top bucket, e.g. "hike 50 or more")

    ``current_upper_pct`` is where the Fed's upper bound sits *before* the meeting; a bucket of
    +25 bps means the new bound is ``current + 0.25``. The ladder is repaired first so no bucket
    can come out negative.
    """
    strikes = sorted(ladder)
    repaired = isotonic_decreasing([ladder[s] for s in strikes])
    fixed = dict(zip(strikes, repaired.tolist(), strict=True))

    buckets: dict[int, float] = {}
    lo, hi = min(bucket_bps), max(bucket_bps)
    for b in bucket_bps:
        level = current_upper_pct + b / 100
        if b == lo:
            buckets[b] = 1.0 - _rung(fixed, level)
        elif b == hi:
            buckets[b] = _rung(fixed, level - STEP_PCT)
        else:
            buckets[b] = _rung(fixed, level - STEP_PCT) - _rung(fixed, level)
    return buckets


def buckets_to_ladder(
    buckets: dict[int, float],
    current_upper_pct: float,
    bucket_bps: tuple[int, ...] = (-50, -25, 0, 25, 50),
) -> dict[float, float]:
    """The reverse: sum bucket probabilities above each bar to get P(rate ends above X)."""
    ladder: dict[float, float] = {}
    ordered = sorted(bucket_bps)
    for i in range(len(ordered) - 1):
        # A bar sitting just below bucket b+1's level is cleared by every bucket above b.
        bar = current_upper_pct + ordered[i + 1] / 100 - STEP_PCT
        ladder[round(bar, 4)] = float(sum(buckets[j] for j in ordered[i + 1 :]))
    return ladder
