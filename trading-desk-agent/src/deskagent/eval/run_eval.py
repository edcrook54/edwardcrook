"""Entry point for `make eval-live`: runs the real agent (a real
`ANTHROPIC_API_KEY` call per question) over every gold question and scores
it with the mechanical metrics in `metrics.py`.

True task-success grading would need an LLM-as-judge (itself another live
API dependency) validated against held-out human judgments - that's PENDING
here, same honesty rule as `llm-news-signal`'s extraction step. What this
script *can* and does compute for real: citation precision (no hallucinated
file paths), tool-usage recall (did it call the tool types the question
actually needs), and keyword recall (a mechanical, not semantic, proxy for
"did the answer touch the right facts").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deskagent.agent.loop import AgentLoop
from deskagent.config import get_settings
from deskagent.eval.metrics import citation_precision, keyword_recall, tool_usage_recall

QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "config" / "eval_questions.json"


def _tools_called(transcript: list[dict[str, Any]]) -> list[str]:
    names = []
    for message in transcript:
        if message.get("role") != "assistant" or not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                names.append(block["name"])
    return names


def run_eval() -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise SystemExit(
            "no ANTHROPIC_API_KEY set - this is the live agent eval, it genuinely needs a "
            "real key (set ANTHROPIC_API_KEY or DESKAGENT_ANTHROPIC_API_KEY)"
        )

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    loop = AgentLoop(client=client, settings=settings)

    questions = json.loads(QUESTIONS_PATH.read_text())
    results = []
    for q in questions:
        result = loop.run(q["question"])
        actual_tools = _tools_called(result.transcript)
        citation = citation_precision(result.transcript, result.answer)
        results.append(
            {
                "id": q["id"],
                "category": q["category"],
                "answer": result.answer,
                "n_tool_calls": result.n_tool_calls,
                "tools_called": actual_tools,
                "hit_max_iterations": result.hit_max_iterations,
                "tool_errors": result.tool_errors,
                "citation_precision": citation["precision"],
                "cited_nothing": citation["cited_nothing"],
                "unsupported_citations": citation["unsupported"],
                "tool_usage_recall": tool_usage_recall(actual_tools, q["expected_tools"]),
                "keyword_recall": keyword_recall(result.answer, q["gold_keywords"]),
                # provenance: which model/transcript produced this row, so a
                # future reader can tell what a given eval_results.json came from
                "model": result.model,
                "transcript_path": str(result.transcript_path),
            }
        )
    return results


def main() -> None:
    results = run_eval()
    for r in results:
        print(
            f"{r['id']:30s} citation_precision={r['citation_precision']:.2f}  "
            f"tool_usage_recall={r['tool_usage_recall']:.2f}  "
            f"keyword_recall={r['keyword_recall']:.2f}"
        )
    n = len(results)
    zero_citation_rate = sum(r["cited_nothing"] for r in results) / n
    print(f"\nmean citation_precision = {sum(r['citation_precision'] for r in results) / n:.3f}")
    print(f"  (of which, cited nothing at all: {zero_citation_rate:.3f} - tracked separately so a")
    print("   rising zero-citation rate can't silently inflate the precision mean)")
    print(f"mean tool_usage_recall  = {sum(r['tool_usage_recall'] for r in results) / n:.3f}")
    print(f"mean keyword_recall     = {sum(r['keyword_recall'] for r in results) / n:.3f}")
    print(f"model = {results[0]['model']!r}" if results else "")

    out_path = Path(__file__).resolve().parents[3] / "data" / "eval_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
