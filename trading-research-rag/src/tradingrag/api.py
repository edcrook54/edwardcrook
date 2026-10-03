from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Query
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel

from tradingrag.config import get_settings
from tradingrag.retrieval.index import HASH_FILE, Index

app = FastAPI(title="trading-research-rag")
app.mount("/metrics", make_asgi_app())

SEARCH_REQUESTS = Counter("tradingrag_search_requests_total", "Search requests", ["mode"])
SEARCH_LATENCY = Histogram("tradingrag_search_latency_seconds", "Search latency", ["mode"])

_cached_index: Index | None = None


class SearchHit(BaseModel):
    source_repo: str
    source_path: str
    section: str
    citation: str
    score: float
    rank: int
    text: str


class SearchResponse(BaseModel):
    query: str
    mode: str
    index_hash: str
    hits: list[SearchHit]


def _load_index() -> Index:
    """Re-checks the on-disk sidecar hash on every call and only re-unpickles
    the (expensive) index when it's actually changed — so a `make index` run
    against a live `make serve` process is picked up on the next request,
    not only after a restart.
    """
    global _cached_index
    settings = get_settings()
    hash_path = settings.index_dir / HASH_FILE
    if not hash_path.exists():
        raise FileNotFoundError(f"no index found at {settings.index_dir}; run `make index` first")
    disk_hash = hash_path.read_text().strip()

    if _cached_index is not None and _cached_index.hash == disk_hash:
        return _cached_index
    _cached_index = Index.load(settings.index_dir)
    return _cached_index


@app.get("/health")
def health() -> dict[str, str]:
    try:
        index = _load_index()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok", "index_hash": index.hash[:12], "n_chunks": str(len(index.chunks))}


@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    mode: str = Query("hybrid", pattern="^(bm25|dense|hybrid)$"),
) -> SearchResponse:
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be empty or whitespace-only")

    try:
        index = _load_index()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    start = time.perf_counter()
    results = index.search(q, top_k=top_k, mode=mode)
    SEARCH_LATENCY.labels(mode=mode).observe(time.perf_counter() - start)
    SEARCH_REQUESTS.labels(mode=mode).inc()

    return SearchResponse(
        query=q,
        mode=mode,
        index_hash=index.hash[:12],
        hits=[
            SearchHit(
                source_repo=r.chunk.source_repo,
                source_path=r.chunk.source_path,
                section=r.chunk.section,
                citation=r.chunk.citation(),
                score=r.score,
                rank=r.rank,
                text=r.chunk.text,
            )
            for r in results
        ],
    )
