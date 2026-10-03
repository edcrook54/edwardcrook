import time
from dataclasses import dataclass
from typing import Any

from deskagent.agent.audit_dispatch import (
    CheckerBrief,
    CheckerFinding,
    dispatch_checkers,
    synthesize,
)


@dataclass
class FakeToolUseBlock:
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class FakeResponse:
    content: list[Any]


class FakeAsyncMessages:
    def __init__(self, responses_by_checker: dict[str, dict[str, Any]], delay: float = 0.0) -> None:
        self._responses_by_checker = responses_by_checker
        self.delay = delay
        self.call_order: list[str] = []

    async def create(self, **kwargs: Any) -> FakeResponse:
        import asyncio

        # identify which checker this is by its system prompt (set to the
        # checker name in these tests, for simplicity)
        checker_name = kwargs["system"]
        self.call_order.append(checker_name)
        if self.delay:
            await asyncio.sleep(self.delay)
        payload = self._responses_by_checker[checker_name]
        return FakeResponse(content=[FakeToolUseBlock(input=payload)])


class FakeAsyncClient:
    def __init__(self, responses_by_checker: dict[str, dict[str, Any]], delay: float = 0.0) -> None:
        self.messages = FakeAsyncMessages(responses_by_checker, delay=delay)


def _empty_finding() -> dict[str, list[str]]:
    return {"critical": [], "important": [], "minor": [], "verified_sound": []}


async def test_dispatch_checkers_runs_all_checkers_concurrently_not_sequentially() -> None:
    briefs = [
        CheckerBrief(name="a", system_prompt="a", context="ctx-a"),
        CheckerBrief(name="b", system_prompt="b", context="ctx-b"),
        CheckerBrief(name="c", system_prompt="c", context="ctx-c"),
    ]
    responses = {name: _empty_finding() for name in "abc"}
    client = FakeAsyncClient(responses, delay=0.05)

    start = time.perf_counter()
    results = await dispatch_checkers(client, briefs, model="test-model")
    elapsed = time.perf_counter() - start

    # three 0.05s calls run concurrently should take ~0.05s total, not ~0.15s
    assert elapsed < 0.12
    assert set(results.keys()) == {"a", "b", "c"}


async def test_dispatch_checkers_returns_the_real_parsed_findings() -> None:
    briefs = [CheckerBrief(name="checker1", system_prompt="checker1", context="ctx")]
    responses = {
        "checker1": {
            "critical": ["a real critical bug"],
            "important": [],
            "minor": [],
            "verified_sound": ["checked X, fine"],
        }
    }
    client = FakeAsyncClient(responses)

    results = await dispatch_checkers(client, briefs, model="test-model")

    assert isinstance(results["checker1"], CheckerFinding)
    assert results["checker1"].critical == ["a real critical bug"]
    assert results["checker1"].verified_sound == ["checked X, fine"]


def test_synthesize_keeps_independent_findings_separate() -> None:
    findings = {
        "checker_a": CheckerFinding(critical=["totally unrelated issue about widgets"]),
        "checker_b": CheckerFinding(important=["a completely different note about gadgets"]),
    }

    result = synthesize(findings)

    assert len(result.critical) == 1
    assert len(result.important) == 1
    assert result.critical[0].convergent is False
    assert result.important[0].convergent is False


def test_synthesize_elevates_convergent_findings_from_different_checkers() -> None:
    # Two checkers describe the same underlying issue in overlapping
    # language from different angles - this should be detected as
    # convergent and combined, taking the more severe tier.
    findings = {
        "checker_a": CheckerFinding(
            important=["missing embargo gap between training window and testing window boundary"]
        ),
        "checker_b": CheckerFinding(
            critical=["no embargo gap exists at the training window testing window boundary split"]
        ),
    }

    result = synthesize(findings)

    assert len(result.critical) == 1
    assert result.critical[0].convergent is True
    assert set(result.critical[0].source_checkers) == {"checker_a", "checker_b"}
    assert len(result.important) == 0  # elevated into critical, not duplicated


def test_synthesize_preserves_all_verified_sound_entries() -> None:
    findings = {
        "checker_a": CheckerFinding(verified_sound=["passed check 1"]),
        "checker_b": CheckerFinding(verified_sound=["passed check 2"]),
    }

    result = synthesize(findings)

    assert set(result.verified_sound) == {"passed check 1", "passed check 2"}


def test_synthesize_handles_no_findings_at_all() -> None:
    result = synthesize({"checker_a": CheckerFinding()})

    assert result.critical == []
    assert result.important == []
    assert result.minor == []
    assert result.verified_sound == []
