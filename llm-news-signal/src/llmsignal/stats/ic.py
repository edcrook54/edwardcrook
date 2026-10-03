"""Rank information coefficient with a Newey-West-corrected significance test,
and Benjamini-Hochberg correction for testing it across multiple horizons.

Why rank-IC, not Pearson correlation on raw returns: a handful of extreme
crypto return days would otherwise dominate a Pearson correlation; Spearman
rank-IC is standard practice in signal research for exactly this reason.
"""

from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from scipy.stats import rankdata


def rank_ic_newey_west(
    scores: np.ndarray, forward_returns: np.ndarray, maxlags: int = 3
) -> dict[str, float]:
    """Spearman rank-IC, plus its Newey-West HAC t-stat and p-value from an
    OLS regression of rank(forward_returns) on rank(scores). The NW
    correction widens the standard error for serial correlation in the
    *returns* (e.g. volatility clustering) that a naive OLS SE would
    understate - it does not, by itself, correct for overlapping event
    windows; see the project's "Scope and limits" for why that doesn't apply
    here (events are spaced further apart than the longest horizon tested).
    """
    scores = np.asarray(scores, dtype=float)
    forward_returns = np.asarray(forward_returns, dtype=float)
    n = len(scores)
    if n < 3:
        raise ValueError("need at least 3 observations for a rank-IC test")

    score_ranks = rankdata(scores)
    return_ranks = rankdata(forward_returns)
    ic = float(np.corrcoef(score_ranks, return_ranks)[0, 1])

    x = sm.add_constant(score_ranks)
    model = sm.OLS(return_ranks, x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    slope_idx = 1
    return {
        "ic": ic,
        "n": float(n),
        "t_stat": float(model.tvalues[slope_idx]),
        "p_value": float(model.pvalues[slope_idx]),
    }


def benjamini_hochberg(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """Returns, per input p-value (same order as given), whether it survives
    Benjamini-Hochberg FDR correction at `alpha` across `len(p_values)` tests.
    """
    n = len(p_values)
    order = np.argsort(p_values)
    sorted_p = np.asarray(p_values)[order]
    thresholds = (np.arange(1, n + 1) / n) * alpha

    below = sorted_p <= thresholds
    if not below.any():
        return [False] * n
    largest_k = int(np.max(np.nonzero(below)[0]))  # largest index where p <= threshold

    significant_sorted = np.zeros(n, dtype=bool)
    significant_sorted[: largest_k + 1] = True

    significant = np.zeros(n, dtype=bool)
    significant[order] = significant_sorted
    return significant.tolist()
