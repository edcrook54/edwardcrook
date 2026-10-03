import math

import pytest

from tradingrag.retrieval.bm25 import BM25Index


def test_single_document_score_matches_hand_worked_formula() -> None:
    # N=1, freq("alpha")=2, doc_len=3, avgdl=3, doc_freq("alpha")=1.
    # idf = ln(1 + (1-1+0.5)/(1+0.5)) = ln(4/3)
    # denom = 2 + 1.5*(0.25 + 0.75*3/3) = 3.5
    # score = idf * (2*2.5) / 3.5 = ln(4/3) * 10/7
    index = BM25Index(["alpha beta alpha"])

    results = index.search("alpha", top_k=1)

    expected = math.log(4 / 3) * (10 / 7)
    assert results == [(0, pytest.approx(expected, rel=1e-9))]


def test_documents_without_the_query_term_score_zero_and_are_excluded() -> None:
    index = BM25Index(["alpha beta", "gamma delta", "alpha alpha gamma"])

    results = index.search("alpha", top_k=10)

    doc_indices = [doc_index for doc_index, _score in results]
    assert doc_indices == [2, 0]  # doc2 has higher term frequency of "alpha"
    assert 1 not in doc_indices


def test_idf_stays_non_negative_for_a_term_in_every_document() -> None:
    # The original Robertson-Walker IDF goes negative once a term appears in
    # more than half the corpus; the ATIRE "+1" variant used here must not.
    index = BM25Index(["alpha shared", "beta shared", "gamma shared"])

    assert index._idf["shared"] >= 0


def test_empty_query_returns_no_results() -> None:
    index = BM25Index(["alpha beta"])

    assert index.search("", top_k=10) == []
