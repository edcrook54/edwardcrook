"""Standard IR metrics, computed directly against binary relevance labels.

Each function takes a single query's ranked retrieved ids and its set of
gold-relevant ids — no hidden state, no dependency on the index — so every
metric is independently testable against a hand-worked example
(`tests/test_eval_metrics.py`).
"""

from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        raise ValueError("relevant set must be non-empty")
    hits = len(set(retrieved[:k]) & relevant)
    return hits / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    hits = len(set(retrieved[:k]) & relevant)
    return hits / k


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    ranked = enumerate(retrieved[:k], start=1)
    dcg = sum(1.0 / math.log2(rank + 1) for rank, doc_id in ranked if doc_id in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def bootstrap_ci(
    values: list[float], n_resamples: int = 2000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float, float]:
    """Percentile bootstrap CI over per-query metric values. Returns (mean, lo, hi)."""
    import random

    if not values:
        raise ValueError("values must be non-empty")
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = int((alpha / 2) * n_resamples)
    hi_idx = int((1 - alpha / 2) * n_resamples) - 1
    return (sum(values) / n, means[lo_idx], means[hi_idx])
