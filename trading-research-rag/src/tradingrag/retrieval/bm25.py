"""Okapi BM25 from scratch — no `rank_bm25` dependency.

Implements the ATIRE IDF variant (`ln(1 + (N - n + 0.5) / (n + 0.5))`), which
stays non-negative for every term instead of going negative for terms that
appear in more than half the corpus, unlike the original Robertson-Walker
formula. Correctness is pinned by `tests/test_bm25.py` against a hand-worked
example, not just "it returns plausible-looking numbers."
"""

from __future__ import annotations

import math
from collections import Counter

from tradingrag.retrieval.tokenize import tokenize

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


class BM25Index:
    def __init__(self, documents: list[str], k1: float = DEFAULT_K1, b: float = DEFAULT_B) -> None:
        self.k1 = k1
        self.b = b
        self._doc_term_counts: list[Counter[str]] = [Counter(tokenize(doc)) for doc in documents]
        self._doc_lengths = [sum(c.values()) for c in self._doc_term_counts]
        self.n_docs = len(documents)
        self.avg_doc_length = (sum(self._doc_lengths) / self.n_docs) if self.n_docs else 0.0

        doc_freq: Counter[str] = Counter()
        for counts in self._doc_term_counts:
            for term in counts:
                doc_freq[term] += 1
        self._idf = {
            term: math.log(1 + (self.n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in doc_freq.items()
        }

    def _score_doc(self, query_terms: list[str], doc_index: int) -> float:
        counts = self._doc_term_counts[doc_index]
        doc_len = self._doc_lengths[doc_index]
        score = 0.0
        for term in query_terms:
            freq = counts.get(term, 0)
            if freq == 0:
                continue
            idf = self._idf.get(term, 0.0)
            denom = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
            score += idf * (freq * (self.k1 + 1)) / denom
        return score

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        query_terms = tokenize(query)
        scores = [(i, self._score_doc(query_terms, i)) for i in range(self.n_docs)]
        scores.sort(key=lambda pair: pair[1], reverse=True)
        return [pair for pair in scores if pair[1] > 0][:top_k]
