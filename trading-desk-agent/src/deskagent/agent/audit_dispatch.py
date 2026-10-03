"""Productionizes this repo's `project-audit` pattern as live, running code:
dispatch N independently-briefed checker agents in parallel (`asyncio`,
genuine concurrency, not sequential calls awaited one after another), each
scoped to exactly the context its lens needs, then synthesize their
findings into one ranked report.

This is deliberately a *simpler* synthesis than a human (or Claude Code)
running the equivalent manual process across the sibling projects: it
flags "convergent" findings via plain keyword-overlap between two
checkers' free-text descriptions (Jaccard similarity over word sets), not
semantic understanding. That's a stated limitation, not a hidden one - see
README "Design decisions".
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field

CHECKER_FINDING_TOOL_SCHEMA: dict[str, Any] = {
    "name": "record_findings",
    "description": "Record this checker's findings after reviewing its assigned material.",
    "input_schema": {
        "type": "object",
        "properties": {
            "critical": {"type": "array", "items": {"type": "string"}},
            "important": {"type": "array", "items": {"type": "string"}},
            "minor": {"type": "array", "items": {"type": "string"}},
            "verified_sound": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Explicit passes - what was checked and found correct.",
            },
        },
        "required": ["critical", "important", "minor", "verified_sound"],
    },
}


class CheckerFinding(BaseModel):
    critical: list[str] = Field(default_factory=list)
    important: list[str] = Field(default_factory=list)
    minor: list[str] = Field(default_factory=list)
    verified_sound: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class CheckerBrief:
    """A self-contained brief for one checker - the system prompt carries
    its lens/checklist, `context` carries only the specific material it
    needs. Deliberately carries nothing about the other checkers or any
    builder's own suspicions, per the project-audit skill's own red flags.
    """

    name: str
    system_prompt: str
    context: str


class _AsyncAnthropicLike(Protocol):
    @property
    def messages(self) -> Any: ...


async def run_checker(
    client: _AsyncAnthropicLike, brief: CheckerBrief, model: str
) -> CheckerFinding:
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=brief.system_prompt,
        tools=[CHECKER_FINDING_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "record_findings"},
        messages=[{"role": "user", "content": brief.context}],
    )
    tool_use = next(block for block in response.content if block.type == "tool_use")
    return CheckerFinding(**tool_use.input)


async def dispatch_checkers(
    client: _AsyncAnthropicLike, briefs: list[CheckerBrief], model: str
) -> dict[str, CheckerFinding]:
    """Runs every checker concurrently via `asyncio.gather` - issuing all
    dispatches in the same turn, not one after another, is the entire point
    of the pattern (a later checker must never be contaminated by an
    earlier one's findings).
    """
    results = await asyncio.gather(*(run_checker(client, brief, model) for brief in briefs))
    return dict(zip((b.name for b in briefs), results, strict=True))


def _word_set(text: str) -> set[str]:
    return {w.strip(".,:;()'\"").lower() for w in text.split() if len(w) > 4}


def _jaccard(a: str, b: str) -> float:
    set_a, set_b = _word_set(a), _word_set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


@dataclass(frozen=True)
class SynthesizedFinding:
    severity: str
    description: str
    source_checkers: list[str]
    convergent: bool


@dataclass(frozen=True)
class SynthesizedAudit:
    critical: list[SynthesizedFinding]
    important: list[SynthesizedFinding]
    minor: list[SynthesizedFinding]
    verified_sound: list[str]


def synthesize(
    findings: dict[str, CheckerFinding], convergence_threshold: float = 0.3
) -> SynthesizedAudit:
    """Cross-references findings across checkers (by text-overlap heuristic)
    before deduplicating, re-ranks by combined severity, and keeps every
    checker's explicit passes - the same rules the manual `project-audit`
    skill uses, applied programmatically.
    """
    all_items: list[tuple[str, str, str]] = []  # (severity, description, checker)
    for checker_name, finding in findings.items():
        for severity, items in (
            ("critical", finding.critical),
            ("important", finding.important),
            ("minor", finding.minor),
        ):
            for item in items:
                all_items.append((severity, item, checker_name))

    synthesized: list[SynthesizedFinding] = []
    consumed: set[int] = set()
    for i, (_severity_i, desc_i, checker_i) in enumerate(all_items):
        if i in consumed:
            continue
        matches = [i]
        for j in range(i + 1, len(all_items)):
            if j in consumed:
                continue
            severity_j, desc_j, checker_j = all_items[j]
            if checker_j != checker_i and _jaccard(desc_i, desc_j) >= convergence_threshold:
                matches.append(j)
        consumed.update(matches)

        source_checkers = [all_items[m][2] for m in matches]
        is_convergent = len(matches) > 1
        # a finding two checkers independently raised is read as at least
        # as severe as the more severe of the two tiers they used.
        severities = [all_items[m][0] for m in matches]
        severity_rank = ("critical", "important", "minor")
        combined_severity = min(severities, key=severity_rank.index)
        description = " | ".join(dict.fromkeys(all_items[m][1] for m in matches))
        synthesized.append(
            SynthesizedFinding(
                severity=combined_severity,
                description=description,
                source_checkers=source_checkers,
                convergent=is_convergent,
            )
        )

    return SynthesizedAudit(
        critical=[f for f in synthesized if f.severity == "critical"],
        important=[f for f in synthesized if f.severity == "important"],
        minor=[f for f in synthesized if f.severity == "minor"],
        verified_sound=[item for finding in findings.values() for item in finding.verified_sound],
    )
