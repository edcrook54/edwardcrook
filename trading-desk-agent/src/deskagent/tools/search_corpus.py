"""Calls `trading-research-rag`'s live `/search` endpoint - a hard
dependency on that project's service running (`make serve` there), not a
reimplementation of its retrieval logic. If the service isn't up, this
raises a clear, actionable error rather than silently returning nothing.
"""

from __future__ import annotations

from typing import Any

import httpx

from deskagent.config import Settings, get_settings


def search_corpus(
    query: str,
    top_k: int = 5,
    mode: str = "hybrid",
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    get = client.get if client is not None else httpx.get
    try:
        response = get(
            settings.search_corpus_url,
            params={"q": query, "top_k": top_k, "mode": mode},
            timeout=10.0,
        )
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"could not reach trading-research-rag at {settings.search_corpus_url} - "
            "is it running? (`make serve` in trading-research-rag/)"
        ) from exc
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return {
        "query": body["query"],
        "hits": [
            {"citation": h["citation"], "text": h["text"], "score": h["score"]}
            for h in body["hits"]
        ],
    }
