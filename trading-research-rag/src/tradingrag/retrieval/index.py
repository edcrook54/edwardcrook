"""Builds, persists, and queries the hybrid index.

The index is content-hashed: `content_hash()` is a SHA-256 over every
chunk's id and text, sorted deterministically. Rebuilding from an unchanged
corpus reproduces the same hash exactly (see
`tests/test_index.py::test_rebuild_is_idempotent`), and `Index.load` refuses
to serve a pickle whose sidecar hash file doesn't match it — a corruption/
tamper check on the saved index artifact itself. That is a narrower
guarantee than it might sound: it does NOT detect corpus drift (someone
editing a source file in `edwardcrook/` after `make index` last ran) —
the old pickle and old hash file still agree perfectly with each other in
that case. Re-running `make index` after any corpus change is still on the
caller; see README "Not yet done".
"""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass
from pathlib import Path

from tradingrag.ingest.chunk import Chunk
from tradingrag.retrieval.bm25 import BM25Index
from tradingrag.retrieval.dense import DenseIndex
from tradingrag.retrieval.fusion import reciprocal_rank_fusion

INDEX_FILE = "index.pkl"
HASH_FILE = "content.sha256"


def content_hash(chunks: list[Chunk]) -> str:
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda c: c.chunk_id):
        digest.update(chunk.chunk_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(chunk.text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    rank: int


class Index:
    def __init__(self, chunks: list[Chunk], svd_components: int = 100, rrf_k: int = 60) -> None:
        if not chunks:
            raise ValueError("cannot build an index from zero chunks")
        self.chunks = chunks
        self.rrf_k = rrf_k
        self.hash = content_hash(chunks)
        texts = [c.text for c in chunks]
        self.bm25 = BM25Index(texts)
        self.dense = DenseIndex(texts, n_components=svd_components)

    def search(self, query: str, top_k: int = 10, mode: str = "hybrid") -> list[SearchResult]:
        pool = max(top_k * 4, 50)
        bm25_ranking = self.bm25.search(query, pool)
        dense_ranking = self.dense.search(query, pool)

        if mode == "bm25":
            ranking = bm25_ranking[:top_k]
        elif mode == "dense":
            ranking = dense_ranking[:top_k]
        elif mode == "hybrid":
            ranking = reciprocal_rank_fusion([bm25_ranking, dense_ranking], k=self.rrf_k)[:top_k]
        else:
            raise ValueError(f"unknown mode: {mode}")

        return [
            SearchResult(chunk=self.chunks[doc_index], score=score, rank=rank)
            for rank, (doc_index, score) in enumerate(ranking, start=1)
        ]

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        with (index_dir / INDEX_FILE).open("wb") as f:
            pickle.dump(self, f)
        (index_dir / HASH_FILE).write_text(self.hash)

    @classmethod
    def load(cls, index_dir: Path) -> Index:
        stored_hash = (index_dir / HASH_FILE).read_text().strip()
        with (index_dir / INDEX_FILE).open("rb") as f:
            index: Index = pickle.load(f)
        if index.hash != stored_hash:
            raise ValueError(
                f"index hash file ({stored_hash}) does not match pickled index ({index.hash}); "
                "rebuild with `make index`"
            )
        return index
