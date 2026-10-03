"""Calls Claude once per statement, via forced tool-use so the output is
schema-validated JSON, not free text to parse.

Every call is cached by a hash of (model, prompt-version, statement text) in
`recorded_responses_path` - not a performance optimization, a determinism
and reproducibility guarantee: re-running `make extract` on unchanged input
must reproduce the exact same scores, and a cached response makes that
trivially true rather than hoping the API returns the same thing twice. That
cache file doubles as the fixture CI replays against, so the test suite
never makes a live network call.

Note: this project was built against an `anthropic` SDK/API version whose
`messages.create` no longer exposes a `temperature` parameter at all (it was
removed from the public API; `output_config.effort` is the closest current
analogue, but it isn't a sampling-randomness knob). Earlier versions of this
module cached on `(model, temperature, text)` from a design written before
that was discovered - there is no live temperature to vary, so determinism
here rests entirely on the cache, not on pinning a sampling parameter.
`PROMPT_VERSION` is bumped whenever the tool schema or instructions change,
so an old cached response is never silently reused across a changed prompt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from llmsignal.extraction.schema import EXTRACTION_TOOL_SCHEMA, ExtractionResult

PROMPT_VERSION = "v1"


def _cache_key(model: str, prompt_version: str, text: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{model}|{prompt_version}|{text}".encode())
    return digest.hexdigest()


class ExtractionClient:
    def __init__(
        self,
        model: str,
        api_key: str | None,
        recorded_responses_path: Path,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.recorded_responses_path = recorded_responses_path
        self.prompt_version = prompt_version
        self._cache: dict[str, dict[str, Any]] = self._load_cache()

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        if self.recorded_responses_path.exists():
            return dict(json.loads(self.recorded_responses_path.read_text()))
        return {}

    def _save_cache(self) -> None:
        self.recorded_responses_path.parent.mkdir(parents=True, exist_ok=True)
        self.recorded_responses_path.write_text(json.dumps(self._cache, indent=2, sort_keys=True))

    def extract(self, statement_excerpt: str) -> tuple[ExtractionResult, dict[str, Any]]:
        """Returns the validated extraction plus metadata (model, prompt_version,
        cache_key, from_cache) so callers can log exactly what produced it.
        """
        key = _cache_key(self.model, self.prompt_version, statement_excerpt)
        metadata: dict[str, Any] = {
            "model": self.model,
            "prompt_version": self.prompt_version,
            "cache_key": key,
        }

        if key in self._cache:
            return ExtractionResult(**self._cache[key]), {**metadata, "from_cache": True}

        if not self.api_key:
            raise RuntimeError(
                "no cached response for this statement and no ANTHROPIC_API_KEY set - "
                "set LLMSIGNAL_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY) to run a live "
                "extraction, or add a recorded response to "
                f"{self.recorded_responses_path}"
            )

        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        # Plain dicts satisfy the SDK's TypedDict params at runtime; mypy strict
        # wants literal TypedDict construction against its Literal-model overloads,
        # which isn't worth fighting for a thin wrapper around an external SDK.
        response = client.messages.create(  # type: ignore[call-overload]
            model=self.model,
            max_tokens=1024,
            tools=[EXTRACTION_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": EXTRACTION_TOOL_SCHEMA["name"]},
            messages=[{"role": "user", "content": statement_excerpt}],
        )
        tool_use = next(block for block in response.content if block.type == "tool_use")
        result = ExtractionResult(**tool_use.input)

        self._cache[key] = result.model_dump()
        self._save_cache()
        return result, {**metadata, "from_cache": False}
