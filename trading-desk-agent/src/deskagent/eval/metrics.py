"""Eval metrics that are genuinely computable from a transcript without an
LLM judge - mechanical, not semantic. True task-success grading (does the
*reasoning* actually answer the question well) needs an LLM-as-judge, which
needs a live API call; that stays PENDING here, same as `llm-news-signal`'s
extraction (see README). These three metrics are the honest, CI-safe subset.
"""

from __future__ import annotations

import re
from typing import Any

_PATH_LIKE_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+")
_TRAILING_PUNCTUATION_RE = re.compile(r"""[.,:;)'"]+$""")


def _extract_clean_paths(text: str) -> set[str]:
    """Path-like tokens (`a/b/c`) with trailing sentence punctuation
    stripped. Matching against the *set* of tokens extracted this same way
    from the evidence (rather than a raw substring check) also makes this
    boundary-aware: a truncated citation like `bar/baz.md` won't falsely
    match evidence that actually contains `foo/bar/baz.md`, because the
    evidence-side extraction pulls out the full `foo/bar/baz.md` token, not
    a shorter one a naive substring check could be fooled by.
    """
    return {_TRAILING_PUNCTUATION_RE.sub("", m) for m in _PATH_LIKE_RE.findall(text)}


def _tool_result_texts(transcript: list[dict[str, Any]]) -> list[str]:
    texts = []
    for message in transcript:
        if message.get("role") != "user" or not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                texts.append(str(block.get("content", "")))
    return texts


def citation_precision(transcript: list[dict[str, Any]], final_answer: str) -> dict[str, Any]:
    """Extracts every path-like token (`a/b/c`) from the final answer and
    checks what fraction appear, as a whole token (not a truncated
    substring), among the path-like tokens in some tool result in the
    transcript - a citation the agent never actually retrieved is a
    hallucinated one. Returns 1.0 (vacuously, with `cited_nothing: True`)
    if the answer cites nothing - that's a different condition from "cited
    things, all verified," and callers should track it separately (see
    `run_eval.py`'s `zero_citation_rate`) rather than letting both collapse
    into the same aggregate mean.
    """
    cited = sorted(_extract_clean_paths(final_answer))
    if not cited:
        return {"precision": 1.0, "cited": [], "unsupported": [], "cited_nothing": True}

    evidence_paths = _extract_clean_paths(" ".join(_tool_result_texts(transcript)))
    supported = [c for c in cited if c in evidence_paths]
    unsupported = [c for c in cited if c not in evidence_paths]
    return {
        "precision": len(supported) / len(cited),
        "cited": cited,
        "unsupported": unsupported,
        "cited_nothing": False,
    }


def tool_usage_recall(actual_tools_called: list[str], expected_tools: list[str]) -> float:
    """Fraction of the expected tool *types* that were actually called at
    least once. Vacuously 1.0 if no tool was expected (e.g. a refusal
    question).
    """
    if not expected_tools:
        return 1.0
    called = set(actual_tools_called)
    expected = set(expected_tools)
    return len(expected & called) / len(expected)


def keyword_recall(answer: str, gold_keywords: list[str]) -> float:
    """Fraction of `gold_keywords` (case-insensitive substrings) present in
    `answer` - a mechanical proxy for task success, not true semantic
    grading. Vacuously 1.0 if there are no keywords to check.
    """
    if not gold_keywords:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in gold_keywords if kw.lower() in answer_lower)
    return hits / len(gold_keywords)
