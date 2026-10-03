import hashlib
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from llmsignal.extraction.client import PROMPT_VERSION, ExtractionClient, _cache_key
from llmsignal.extraction.schema import EXTRACTION_TOOL_SCHEMA, ExtractionResult

# Pins each prompt_version to a hash of the schema it was built against, so
# changing EXTRACTION_TOOL_SCHEMA without bumping PROMPT_VERSION fails loudly
# here instead of silently letting old cached responses be reused as if they
# came from the new prompt.
_SCHEMA_HASH_BY_VERSION = {
    "v1": "21f829f77847e394d3a2292353f778817d0caf77e4db6c79f3c9890b1f1fb88a",
}


def test_prompt_version_is_pinned_to_the_current_schema_content() -> None:
    schema_hash = hashlib.sha256(json.dumps(EXTRACTION_TOOL_SCHEMA, sort_keys=True).encode())
    expected = _SCHEMA_HASH_BY_VERSION.get(PROMPT_VERSION)
    assert expected is not None, (
        f"PROMPT_VERSION={PROMPT_VERSION!r} has no pinned schema hash - add one to "
        "_SCHEMA_HASH_BY_VERSION in this test (and bump PROMPT_VERSION if the schema "
        "changed on purpose)"
    )
    assert schema_hash.hexdigest() == expected, (
        "EXTRACTION_TOOL_SCHEMA changed without bumping PROMPT_VERSION - old cached "
        "responses would be silently reused as if they came from the new prompt"
    )


def test_anthropic_sdk_still_has_no_temperature_parameter() -> None:
    """Pins the fact this project's determinism story relies on: the
    installed anthropic SDK's Messages.create has no sampling-randomness
    knob. If this starts failing, the SDK added one back - reconsider the
    determinism design (see client.py's module docstring) rather than just
    deleting this test.
    """
    from anthropic.resources.messages import Messages

    params = inspect.signature(Messages.create).parameters
    assert "temperature" not in params
    assert "seed" not in params


def test_cache_key_is_deterministic_and_input_sensitive() -> None:
    key_a = _cache_key("model-x", "v1", "some statement text")
    key_b = _cache_key("model-x", "v1", "some statement text")
    key_c = _cache_key("model-x", "v1", "different statement text")
    key_d = _cache_key("model-y", "v1", "some statement text")
    key_e = _cache_key("model-x", "v2", "some statement text")

    assert key_a == key_b
    assert key_a != key_c
    assert key_a != key_d
    assert key_a != key_e


def test_extract_returns_cached_result_without_any_api_key(tmp_path: Path) -> None:
    cache_path = tmp_path / "recorded.json"
    text = "The Committee decided to maintain the target range."
    key = _cache_key("test-model", "v1", text)
    cache_path.write_text(
        f'{{"{key}": {{"hawkish_dovish_score": 0.3, "surprise_magnitude": 0.1, '
        f'"sentiment": "hawkish", "confidence": 0.8, "rationale": "steady guidance"}}}}'
    )
    client = ExtractionClient(
        model="test-model", api_key=None, recorded_responses_path=cache_path, prompt_version="v1"
    )

    result, metadata = client.extract(text)

    assert isinstance(result, ExtractionResult)
    assert result.hawkish_dovish_score == 0.3
    assert metadata["from_cache"] is True


def test_extract_raises_a_clear_error_when_uncached_and_no_api_key(tmp_path: Path) -> None:
    client = ExtractionClient(
        model="test-model",
        api_key=None,
        recorded_responses_path=tmp_path / "recorded.json",
    )

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        client.extract("a statement never seen before")


def test_extraction_result_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        ExtractionResult(
            hawkish_dovish_score=1.5,  # out of [-1, 1]
            surprise_magnitude=0.2,
            sentiment="hawkish",
            confidence=0.9,
            rationale="x",
        )


def test_extraction_result_rejects_invalid_sentiment_label() -> None:
    with pytest.raises(ValidationError):
        ExtractionResult(
            hawkish_dovish_score=0.2,
            surprise_magnitude=0.2,
            sentiment="very hawkish",  # not one of the enum values
            confidence=0.9,
            rationale="x",
        )
