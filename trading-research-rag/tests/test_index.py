from pathlib import Path

import pytest

from tradingrag.ingest.chunk import Chunk
from tradingrag.retrieval.index import Index, content_hash


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        source_repo="myproj",
        source_path="README.md",
        section="Results",
    )


def test_rebuild_from_unchanged_corpus_is_idempotent() -> None:
    chunks_a = [_chunk("1", "alpha beta"), _chunk("2", "gamma delta")]
    chunks_b = [_chunk("2", "gamma delta"), _chunk("1", "alpha beta")]  # different order

    assert content_hash(chunks_a) == content_hash(chunks_b)


def test_hash_changes_when_a_chunk_changes() -> None:
    chunks = [_chunk("1", "alpha beta")]
    changed = [_chunk("1", "alpha beta gamma")]

    assert content_hash(chunks) != content_hash(changed)


def test_save_then_load_roundtrips_and_serves_queries(tmp_path: Path) -> None:
    chunks = [
        _chunk("1", "kalman filter hedge ratio estimation"),
        _chunk("2", "grafana prometheus dashboard metrics"),
    ]
    index = Index(chunks, svd_components=1)
    index_dir = tmp_path / "index"
    index.save(index_dir)

    loaded = Index.load(index_dir)

    results = loaded.search("kalman filter", top_k=1, mode="bm25")
    assert results[0].chunk.chunk_id == "1"


def test_load_rejects_a_hash_file_that_does_not_match_the_pickled_index(tmp_path: Path) -> None:
    chunks = [_chunk("1", "alpha beta")]
    index = Index(chunks, svd_components=1)
    index_dir = tmp_path / "index"
    index.save(index_dir)
    (index_dir / "content.sha256").write_text("not-the-real-hash")

    with pytest.raises(ValueError, match="does not match"):
        Index.load(index_dir)


def test_building_an_index_from_zero_chunks_raises() -> None:
    with pytest.raises(ValueError, match="zero chunks"):
        Index([])
