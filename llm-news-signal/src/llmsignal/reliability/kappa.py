"""Validates the LLM as a labeler against held-out human labels.

This project's non-negotiable rule: the LLM is treated as a noisy labeler
whose reliability must be measured, not assumed, exactly the same way any
other labeling source would be validated before trusting its output in a
downstream statistical test.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.stats import pearsonr


def cohens_kappa(rater_a: list[str], rater_b: list[str]) -> float:
    """Standard Cohen's kappa for categorical agreement between two raters:
    `(p_observed - p_expected) / (1 - p_expected)`, where `p_expected` is the
    chance-agreement rate implied by each rater's own marginal label
    frequencies.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError("raters must have the same number of labels")
    n = len(rater_a)
    if n == 0:
        raise ValueError("need at least one labeled pair")

    p_observed = sum(a == b for a, b in zip(rater_a, rater_b, strict=True)) / n

    counts_a = Counter(rater_a)
    counts_b = Counter(rater_b)
    categories = set(counts_a) | set(counts_b)
    p_expected = sum((counts_a.get(c, 0) / n) * (counts_b.get(c, 0) / n) for c in categories)

    if p_expected == 1.0:
        return 1.0 if p_observed == 1.0 else 0.0
    return (p_observed - p_expected) / (1 - p_expected)


def continuous_agreement(llm_scores: list[float], human_scores: list[float]) -> dict[str, float]:
    """Pearson correlation, mean absolute error, and mean signed bias between
    the LLM's continuous score and a human labeler's score on the same
    held-out examples.
    """
    llm = np.asarray(llm_scores, dtype=float)
    human = np.asarray(human_scores, dtype=float)
    if len(llm) != len(human):
        raise ValueError("llm_scores and human_scores must be the same length")
    if len(llm) < 2:
        raise ValueError("need at least 2 pairs to compute correlation")

    correlation, _p_value = pearsonr(llm, human)
    return {
        "pearson_r": float(correlation),
        "mae": float(np.mean(np.abs(llm - human))),
        "bias": float(np.mean(llm - human)),
        "n": float(len(llm)),
    }
