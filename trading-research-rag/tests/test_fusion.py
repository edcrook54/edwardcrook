import pytest

from tradingrag.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_matches_hand_worked_example() -> None:
    # doc 1 ranked 1st by bm25, 2nd by dense; doc 2 ranked 2nd by bm25, 1st by dense.
    # With k=0: rrf(1) = 1/1 + 1/2 = 1.5, rrf(2) = 1/2 + 1/1 = 1.5 -> tie.
    bm25_ranking = [(1, 5.0), (2, 3.0)]
    dense_ranking = [(2, 0.9), (1, 0.8)]

    fused = reciprocal_rank_fusion([bm25_ranking, dense_ranking], k=0)

    assert dict(fused) == pytest.approx({1: 1.5, 2: 1.5})


def test_rrf_favours_a_document_ranked_highly_by_both_lists() -> None:
    bm25_ranking = [(1, 5.0), (2, 4.0), (3, 3.0)]
    dense_ranking = [(1, 0.9), (3, 0.8), (2, 0.7)]

    fused = reciprocal_rank_fusion([bm25_ranking, dense_ranking], k=60)

    ranked_ids = [doc_index for doc_index, _score in fused]
    assert ranked_ids[0] == 1  # ranked 1st in both lists


def test_document_missing_from_one_list_is_still_included() -> None:
    bm25_ranking = [(1, 5.0)]
    dense_ranking: list[tuple[int, float]] = []

    fused = reciprocal_rank_fusion([bm25_ranking, dense_ranking], k=60)

    assert fused == [(1, pytest.approx(1 / 61))]
