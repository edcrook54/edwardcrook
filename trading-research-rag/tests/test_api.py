from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tradingrag import api
from tradingrag.config import Settings
from tradingrag.ingest.chunk import Chunk
from tradingrag.retrieval.index import Index


def _build_tiny_index(index_dir: Path, extra_chunk: bool = False) -> None:
    chunks = [
        Chunk(
            chunk_id="proj/a.md::0::Intro",
            text="kalman filter hedge ratio estimation",
            source_repo="proj",
            source_path="a.md",
            section="Intro",
        ),
        Chunk(
            chunk_id="proj/b.md::0::Other",
            text="grafana prometheus dashboard",
            source_repo="proj",
            source_path="b.md",
            section="Other",
        ),
    ]
    if extra_chunk:
        chunks.append(
            Chunk(
                chunk_id="proj/c.md::0::New",
                text="a brand new chunk added after rebuild",
                source_repo="proj",
                source_path="c.md",
                section="New",
            )
        )
    Index(chunks, svd_components=1).save(index_dir)


@pytest.fixture(autouse=True)
def _reset_index_cache() -> None:
    api._cached_index = None
    yield
    api._cached_index = None


@pytest.fixture
def client_with_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    index_dir = tmp_path / "index"
    _build_tiny_index(index_dir)
    settings = Settings(corpus_roots=[], index_dir=index_dir)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    return TestClient(api.app)


def test_health_returns_503_with_actionable_message_when_no_index_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(corpus_roots=[], index_dir=tmp_path / "missing")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    client = TestClient(api.app)

    response = client.get("/health")

    assert response.status_code == 503
    assert "make index" in response.json()["detail"]


def test_health_ok_after_index_built(client_with_index: TestClient) -> None:
    response = client_with_index.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["n_chunks"] == "2"


def test_search_rejects_whitespace_only_query(client_with_index: TestClient) -> None:
    assert client_with_index.get("/search", params={"q": "   "}).status_code == 422


def test_search_rejects_empty_query(client_with_index: TestClient) -> None:
    assert client_with_index.get("/search", params={"q": ""}).status_code == 422


def test_search_rejects_invalid_mode(client_with_index: TestClient) -> None:
    response = client_with_index.get("/search", params={"q": "kalman", "mode": "magic"})
    assert response.status_code == 422


def test_search_rejects_top_k_out_of_bounds(client_with_index: TestClient) -> None:
    assert client_with_index.get("/search", params={"q": "kalman", "top_k": 0}).status_code == 422
    assert client_with_index.get("/search", params={"q": "kalman", "top_k": 51}).status_code == 422


def test_search_returns_a_real_citation(client_with_index: TestClient) -> None:
    response = client_with_index.get("/search", params={"q": "kalman filter", "mode": "bm25"})

    assert response.status_code == 200
    hits = response.json()["hits"]
    assert hits[0]["citation"] == "proj/a.md (Intro)"


def test_metrics_endpoint_is_live_after_a_real_request(client_with_index: TestClient) -> None:
    client_with_index.get("/search", params={"q": "kalman"})

    response = client_with_index.get("/metrics", follow_redirects=True)

    assert response.status_code == 200
    assert "tradingrag_search_requests_total" in response.text


def test_rebuilt_index_is_picked_up_without_a_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_dir = tmp_path / "index"
    _build_tiny_index(index_dir)
    settings = Settings(corpus_roots=[], index_dir=index_dir)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    client = TestClient(api.app)
    first_hash = client.get("/health").json()["index_hash"]

    _build_tiny_index(index_dir, extra_chunk=True)  # simulate `make index` while serving

    health = client.get("/health").json()
    assert health["index_hash"] != first_hash
    assert health["n_chunks"] == "3"
