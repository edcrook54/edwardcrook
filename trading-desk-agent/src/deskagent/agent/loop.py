"""A bounded, tool-use agent loop over the four sandboxed tools.

Deliberately built on the raw Anthropic API (`client.messages.create`), not
a framework - consistent with this repo's "derive from scratch" house
style and the explicit choice (see README) to keep the agent's control flow
inspectable in ~100 lines rather than behind a framework's abstractions.

The `client` parameter is always injectable (a duck-typed object exposing
`.messages.create(...)`), which is what makes this fully testable without
a live `ANTHROPIC_API_KEY` - see `tests/test_agent_loop.py`'s scripted fake
client.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from prometheus_client import Counter, Histogram

from deskagent.agent.schemas import ALL_TOOL_SCHEMAS
from deskagent.config import Settings, get_settings
from deskagent.tools import get_file, rerun_backtest_variant, run_stat_test, search_corpus

SYSTEM_PROMPT = (
    "You are a research-desk assistant over this repo's own quant projects "
    "(crypto-cointegration-signal, pm-bayes-pricer, trading-research-rag, "
    "llm-news-signal). Use the tools to find real evidence before answering - "
    "never state a specific number, citation, or file path you haven't actually "
    "retrieved via a tool in this conversation. Every factual claim must trace "
    "to a specific tool result; say so plainly if the tools don't support an "
    "answer, rather than guessing."
)

TOOL_REGISTRY: dict[str, Any] = {
    "search_corpus": search_corpus,
    "run_stat_test": run_stat_test,
    "rerun_backtest_variant": rerun_backtest_variant,
    "get_file": get_file,
}

AGENT_REQUESTS = Counter("deskagent_requests_total", "Agent loop invocations", ["stop_reason"])
AGENT_TOOL_CALLS = Counter("deskagent_tool_calls_total", "Tool calls made by the agent", ["tool"])
AGENT_LATENCY = Histogram("deskagent_latency_seconds", "End-to-end agent loop latency")
AGENT_TOKENS = Counter("deskagent_tokens_total", "Tokens used", ["direction"])


class _AnthropicLike(Protocol):
    @property
    def messages(self) -> Any: ...


@dataclass
class AgentResult:
    answer: str
    transcript: list[dict[str, Any]]
    n_iterations: int
    n_tool_calls: int
    stop_reason: str
    input_tokens: int
    output_tokens: int
    model: str
    transcript_path: Path
    hit_max_iterations: bool = False
    tool_errors: list[str] = field(default_factory=list)


class AgentLoop:
    def __init__(
        self,
        client: _AnthropicLike,
        settings: Settings | None = None,
        tool_registry: dict[str, Any] | None = None,
    ) -> None:
        self.client = client
        self.settings = settings or get_settings()
        self.tool_registry = tool_registry or TOOL_REGISTRY

    def _dispatch_tool(self, name: str, tool_input: dict[str, Any]) -> tuple[Any, str | None]:
        if name not in self.tool_registry:
            return None, f"unknown tool: {name!r}"
        try:
            result = self.tool_registry[name](**tool_input)
            return result, None
        except Exception as exc:  # noqa: BLE001 - genuinely any tool error must become a tool_result, not crash the loop
            return None, f"{type(exc).__name__}: {exc}"

    def run(self, question: str) -> AgentResult:
        start = time.perf_counter()
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        transcript: list[dict[str, Any]] = [{"role": "user", "content": question}]
        n_tool_calls = 0
        tool_errors: list[str] = []
        total_input_tokens = 0
        total_output_tokens = 0
        stop_reason = "unknown"

        for _iteration in range(self.settings.max_iterations):
            response = self.client.messages.create(
                model=self.settings.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=ALL_TOOL_SCHEMAS,
                messages=messages,
            )
            total_input_tokens += getattr(response.usage, "input_tokens", 0)
            total_output_tokens += getattr(response.usage, "output_tokens", 0)
            stop_reason = response.stop_reason

            assistant_content = [_block_to_dict(b) for b in response.content]
            messages.append({"role": "assistant", "content": response.content})
            transcript.append({"role": "assistant", "content": assistant_content})

            if stop_reason != "tool_use":
                answer = next((b["text"] for b in assistant_content if b.get("type") == "text"), "")
                transcript_path = self._write_transcript(transcript)
                AGENT_REQUESTS.labels(stop_reason=stop_reason).inc()
                AGENT_TOKENS.labels(direction="input").inc(total_input_tokens)
                AGENT_TOKENS.labels(direction="output").inc(total_output_tokens)
                AGENT_LATENCY.observe(time.perf_counter() - start)
                return AgentResult(
                    answer=answer,
                    transcript=transcript,
                    n_iterations=_iteration + 1,
                    n_tool_calls=n_tool_calls,
                    stop_reason=stop_reason,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    model=self.settings.model,
                    transcript_path=transcript_path,
                    tool_errors=tool_errors,
                )

            tool_results = []
            for block in assistant_content:
                if block.get("type") != "tool_use":
                    continue
                n_tool_calls += 1
                AGENT_TOOL_CALLS.labels(tool=block["name"]).inc()
                result, error = self._dispatch_tool(block["name"], block["input"])
                if error:
                    tool_errors.append(f"{block['name']}: {error}")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(result if error is None else {"error": error}),
                        "is_error": error is not None,
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            transcript.append({"role": "user", "content": tool_results})

        transcript_path = self._write_transcript(transcript)
        AGENT_REQUESTS.labels(stop_reason="max_iterations").inc()
        return AgentResult(
            answer="(hit max_iterations without a final answer)",
            transcript=transcript,
            n_iterations=self.settings.max_iterations,
            n_tool_calls=n_tool_calls,
            stop_reason="max_iterations",
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            model=self.settings.model,
            transcript_path=transcript_path,
            hit_max_iterations=True,
            tool_errors=tool_errors,
        )

    def _write_transcript(self, transcript: list[dict[str, Any]]) -> Path:
        self.settings.transcript_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.transcript_dir / f"{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(transcript, default=str, indent=2))
        return path


def _block_to_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return dict(block.model_dump())
    # Minimal fallback for duck-typed (e.g. test fake) blocks that are
    # neither a dict nor a pydantic model - keep every field the loop
    # actually reads downstream (text/name/input/id), not just `type`.
    result: dict[str, Any] = {"type": getattr(block, "type", "unknown")}
    for attr in ("text", "name", "input", "id"):
        if hasattr(block, attr):
            result[attr] = getattr(block, attr)
    return result
