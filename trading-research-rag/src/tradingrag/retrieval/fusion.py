"""Reciprocal rank fusion: combine two rankings using rank position only.

RRF is used (rather than a weighted score blend) because BM25 and LSA cosine
scores live on incomparable scales — fusing them by raw score would silently
let whichever method happens to produce larger numbers dominate.
"""

from __future__ import annotations


def reciprocal_rank_fusion(
    rankings: list[list[tuple[int, float]]], k: int = 60
) -> list[tuple[int, float]]:
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, (doc_index, _score) in enumerate(ranking, start=1):
            fused[doc_index] = fused.get(doc_index, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)
