import httpx
import pytest

from deskagent.config import Settings
from deskagent.tools.search_corpus import search_corpus


def _mock_client(response_json: dict, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=response_json)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_corpus_returns_hits_from_a_mocked_service() -> None:
    settings = Settings(search_corpus_url="http://fake/search")
    mock_response = {
        "query": "hedge ratio",
        "mode": "hybrid",
        "index_hash": "abc123",
        "hits": [
            {
                "source_repo": "crypto-cointegration-signal",
                "source_path": "notebooks/04_backtest.ipynb",
                "section": "Kalman-filtered hedge ratio",
                "citation": "crypto-cointegration-signal/notebooks/04_backtest.ipynb (cell 4)",
                "score": 0.03,
                "rank": 1,
                "text": "some retrieved text",
            }
        ],
    }
    client = _mock_client(mock_response)

    result = search_corpus("hedge ratio", settings=settings, client=client)

    assert result["query"] == "hedge ratio"
    assert len(result["hits"]) == 1
    assert result["hits"][0]["citation"] == mock_response["hits"][0]["citation"]


def test_search_corpus_raises_a_clear_error_when_service_is_unreachable() -> None:
    settings = Settings(search_corpus_url="http://127.0.0.1:1/search")  # nothing listens here

    with pytest.raises(RuntimeError, match="could not reach trading-research-rag"):
        search_corpus("anything", settings=settings)


def test_search_corpus_raises_on_a_server_error() -> None:
    settings = Settings(search_corpus_url="http://fake/search")
    client = _mock_client({"detail": "boom"}, status_code=503)

    with pytest.raises(httpx.HTTPStatusError):
        search_corpus("anything", settings=settings, client=client)
