from tradingrag.retrieval.dense import DenseIndex


def test_query_ranks_topically_similar_document_above_unrelated_one() -> None:
    documents = [
        "the kalman filter estimates a time varying hedge ratio for the pair",
        "cointegration test on dollar bars for crypto pairs trading",
        "grafana dashboards show prometheus metrics for the live pricer",
    ]
    index = DenseIndex(documents, n_components=2)

    results = index.search("time varying hedge ratio estimation", top_k=3)

    ranked_doc_indices = [doc_index for doc_index, _score in results]
    assert ranked_doc_indices[0] == 0


def test_scores_are_bounded_cosine_similarities() -> None:
    documents = ["alpha beta gamma", "delta epsilon zeta", "alpha beta gamma delta"]
    index = DenseIndex(documents, n_components=2)

    results = index.search("alpha beta", top_k=3)

    assert all(-1.0 - 1e-9 <= score <= 1.0 + 1e-9 for _doc_index, score in results)


def test_n_components_is_capped_below_vocab_and_doc_count() -> None:
    # Only 2 tiny documents and a handful of terms: requesting 100 SVD
    # components must not raise, it should silently clamp instead.
    index = DenseIndex(["alpha beta", "gamma delta"], n_components=100)

    results = index.search("alpha", top_k=2)

    assert len(results) >= 1
