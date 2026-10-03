import math

import pytest

from tradingrag.eval.metrics import (
    bootstrap_ci,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_counts_hits_within_cutoff() -> None:
    retrieved = ["a", "b", "c", "d"]
    relevant = {"b", "d", "z"}  # z is relevant but never retrieved

    assert recall_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 3)  # only b found in top 2
    assert recall_at_k(retrieved, relevant, k=4) == pytest.approx(2 / 3)  # b and d found


def test_precision_at_k() -> None:
    retrieved = ["a", "b", "c"]
    relevant = {"b"}

    assert precision_at_k(retrieved, relevant, k=3) == pytest.approx(1 / 3)
    assert precision_at_k(retrieved, relevant, k=0) == 0.0


def test_reciprocal_rank_uses_first_hit_only() -> None:
    assert reciprocal_rank(["a", "b", "c"], {"c"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(["a", "b", "c"], {"b", "c"}) == pytest.approx(1 / 2)
    assert reciprocal_rank(["a", "b"], {"z"}) == 0.0


def test_ndcg_matches_hand_worked_example() -> None:
    # relevant = {a, c}; retrieved = [a, b, c] -> hits at rank 1 and 3.
    # DCG = 1/log2(2) + 1/log2(4) = 1 + 0.5 = 1.5
    # Ideal ranking puts both relevant docs first: IDCG = 1/log2(2) + 1/log2(3)
    retrieved = ["a", "b", "c"]
    relevant = {"a", "c"}

    expected_dcg = 1.0 / math.log2(2) + 1.0 / math.log2(4)
    expected_idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)

    assert ndcg_at_k(retrieved, relevant, k=3) == pytest.approx(expected_dcg / expected_idcg)


def test_ndcg_is_one_for_a_perfect_ranking() -> None:
    assert ndcg_at_k(["a", "b"], {"a", "b"}, k=2) == pytest.approx(1.0)


def test_ndcg_is_zero_when_nothing_relevant_is_retrieved() -> None:
    assert ndcg_at_k(["x", "y"], {"a"}, k=2) == 0.0


def test_recall_rejects_empty_relevant_set() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        recall_at_k(["a"], set(), k=1)


def test_bootstrap_ci_contains_the_sample_mean_and_widens_with_more_spread() -> None:
    tight = [0.5, 0.5, 0.5, 0.5]
    spread = [0.0, 1.0, 0.0, 1.0]

    mean_tight, lo_tight, hi_tight = bootstrap_ci(tight, n_resamples=500, seed=1)
    mean_spread, lo_spread, hi_spread = bootstrap_ci(spread, n_resamples=500, seed=1)

    assert mean_tight == pytest.approx(0.5)
    assert lo_tight <= mean_tight <= hi_tight
    assert (hi_spread - lo_spread) > (hi_tight - lo_tight)
