from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deskagent.agent.loop import AgentLoop
from deskagent.config import Settings


@dataclass
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 5


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class FakeResponse:
    content: list[Any]
    stop_reason: str
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeMessages:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = iter(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        # snapshot `messages` (a shallow copy of the list itself) - the real
        # loop keeps mutating the same list object across iterations, so
        # recording the live reference would make every past call's
        # `.messages` retroactively show the final iteration's state.
        snapshot = {**kwargs, "messages": list(kwargs["messages"])}
        self.calls.append(snapshot)
        return next(self._responses)


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.messages = FakeMessages(responses)


def _settings(tmp_path: Path, max_iterations: int = 8) -> Settings:
    return Settings(transcript_dir=tmp_path / "transcripts", max_iterations=max_iterations)


def test_agent_answers_directly_without_any_tool_call(tmp_path: Path) -> None:
    client = FakeClient(
        [FakeResponse(content=[FakeTextBlock("the answer")], stop_reason="end_turn")]
    )
    loop = AgentLoop(client=client, settings=_settings(tmp_path))

    result = loop.run("a simple question")

    assert result.answer == "the answer"
    assert result.n_tool_calls == 0
    assert result.n_iterations == 1
    assert result.stop_reason == "end_turn"
    assert not result.hit_max_iterations
    assert (tmp_path / "transcripts").exists()


def test_agent_calls_a_real_tool_then_answers(tmp_path: Path) -> None:
    series = [0.01, 0.02, -0.01, 0.015, 0.005, 0.02, -0.005, 0.01]
    client = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeToolUseBlock(
                        id="t1",
                        name="run_stat_test",
                        input={"test": "newey_west_mean", "series_a": series},
                    )
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeTextBlock("the mean is small")], stop_reason="end_turn"),
        ]
    )
    loop = AgentLoop(client=client, settings=_settings(tmp_path))

    result = loop.run("what's the mean of this series?")

    assert result.n_tool_calls == 1
    assert result.answer == "the mean is small"
    assert result.tool_errors == []
    # the tool result for the first iteration must be a real computed value,
    # not a stub - check it made it into the transcript sent back to the model
    tool_result_message = loop.client.messages.calls[1]["messages"][-1]
    assert tool_result_message["role"] == "user"
    assert '"test": "newey_west_mean"' in tool_result_message["content"][0]["content"]


def test_agent_handles_an_unknown_tool_name_without_crashing(tmp_path: Path) -> None:
    client = FakeClient(
        [
            FakeResponse(
                content=[FakeToolUseBlock(id="t1", name="not_a_real_tool", input={})],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeTextBlock("recovered")], stop_reason="end_turn"),
        ]
    )
    loop = AgentLoop(client=client, settings=_settings(tmp_path))

    result = loop.run("call a bad tool")

    assert result.answer == "recovered"
    assert len(result.tool_errors) == 1
    assert "unknown tool" in result.tool_errors[0]


def test_agent_handles_a_tool_that_raises_without_crashing(tmp_path: Path) -> None:
    client = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeToolUseBlock(
                        id="t1",
                        name="get_file",
                        input={"relative_path": "pm-bayes-pricer/does-not-exist.md"},
                    )
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeTextBlock("file was missing")], stop_reason="end_turn"),
        ]
    )
    loop = AgentLoop(client=client, settings=_settings(tmp_path))

    result = loop.run("read a file that doesn't exist")

    assert result.answer == "file was missing"
    assert len(result.tool_errors) == 1
    assert "get_file" in result.tool_errors[0]


def test_agent_stops_at_max_iterations_rather_than_looping_forever(tmp_path: Path) -> None:
    # every response keeps asking for another tool call, never answering
    responses = [
        FakeResponse(
            content=[FakeToolUseBlock(id=f"t{i}", name="not_a_real_tool", input={})],
            stop_reason="tool_use",
        )
        for i in range(5)
    ]
    client = FakeClient(responses)
    loop = AgentLoop(client=client, settings=_settings(tmp_path, max_iterations=3))

    result = loop.run("never-ending question")

    assert result.hit_max_iterations is True
    assert result.stop_reason == "max_iterations"
    assert result.n_iterations == 3
    assert len(client.messages.calls) == 3


def test_agent_dispatches_a_second_real_tool_end_to_end(tmp_path: Path) -> None:
    # exercises get_file against the real whitelisted filesystem, not a stub
    client = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeToolUseBlock(
                        id="t1",
                        name="get_file",
                        input={"relative_path": "pm-bayes-pricer/README.md"},
                    )
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeTextBlock("read it")], stop_reason="end_turn"),
        ]
    )
    loop = AgentLoop(client=client, settings=_settings(tmp_path))

    result = loop.run("read the pm-bayes-pricer README")

    assert result.tool_errors == []
    tool_result_message = loop.client.messages.calls[1]["messages"][-1]
    assert "pm-bayes-pricer" in tool_result_message["content"][0]["content"]
