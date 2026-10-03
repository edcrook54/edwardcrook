"""The "semantic" leg of the hybrid: TF-IDF + truncated SVD (classic LSA).

Deliberately not a neural embedding model. At this corpus size (a few
thousand chunks drawn from two of my own projects) a GPU/API-dependent
embedding model buys nothing a reviewer could verify by re-running `make
eval` offline, and it would hide exactly the kind of "why did this chunk
rank here" reasoning LSA keeps transparent (literally a weighted sum of
term co-occurrence directions). If the eval notebook ever shows LSA is the
retrieval bottleneck, swapping in `sentence-transformers` is a contained
change behind this same `DenseIndex` interface — see "Not yet done" in the
README.
"""

from __future__ import annotations

from typing import cast

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from tradingrag.retrieval.tokenize import tokenize


class DenseIndex:
    def __init__(
        self, documents: list[str], n_components: int = 100, random_state: int = 0
    ) -> None:
        self.vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, lowercase=False)
        tfidf = self.vectorizer.fit_transform(documents)

        n_components = min(n_components, max(1, min(tfidf.shape) - 1))
        self.svd = TruncatedSVD(n_components=n_components, random_state=random_state)
        doc_vectors = self.svd.fit_transform(tfidf)
        self._doc_vectors = _l2_normalize(doc_vectors)
        self.n_docs = len(documents)

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        query_tfidf = self.vectorizer.transform([query])
        query_vector = _l2_normalize(self.svd.transform(query_tfidf))[0]
        scores = self._doc_vectors @ query_vector
        order = np.argsort(-scores)[:top_k]
        return [(int(i), float(scores[i])) for i in order if scores[i] > 0]


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return cast(np.ndarray, matrix / norms)
