---
name: hallucination-citation-checker
description: Use when reviewing an agent's final answers for claims not actually backed by tool output, or citations it never actually retrieved - triggers on "hallucination", "citation precision", "unsupported claim", "ungrounded answer".
---

# Hallucination/Citation Checker

## Overview

This agent's entire value proposition is that every factual claim traces
to a real tool call in that conversation. This skill checks whether that's
actually true - in the `citation_precision` metric's implementation, and
(once real transcripts exist) in sampled real transcripts themselves.

## When to Use

Before trusting `citation_precision` as a meaningful signal, and before
accepting any agent answer (real or scripted-for-testing) as properly
grounded.

## Core Checklist

### 1. Does `citation_precision` actually catch what it claims to?

- Trace `_PATH_LIKE_RE` in `eval/metrics.py` against real citation formats
  actually produced by `search_corpus` (e.g.
  `"crypto-cointegration-signal/notebooks/04_backtest.ipynb (cell 4)"`) -
  confirm the regex extracts the path portion correctly and doesn't,
  say, truncate at the first slash or miss paths with underscores/digits.
- Confirm the "evidence" pool `citation_precision` checks against is built
  from *all* tool results in the transcript, not just `search_corpus`
  results - an answer citing `pm-bayes-pricer/README.md` after a `get_file`
  call (not a `search_corpus` call) must still count as supported.
- Verify the vacuous-pass case (`cited == []` returns precision 1.0) is
  actually the right default - an answer with zero citations isn't
  hallucinating a citation, but check the eval doesn't silently treat "no
  citations attempted" as equivalent to "fully grounded" in any aggregate
  reporting (these are different and should probably be visible as a
  separate rate, e.g. what fraction of answers attempted zero citations).

### 2. Claims beyond citations

- `citation_precision` only catches *path-like* hallucinations. A claim
  like "the kappa threshold is 0.5" when the real tool result said 0.4 is a
  different kind of hallucination (a wrong fact, correctly cited) that this
  metric cannot catch. Confirm the README/CLAUDE.md are honest that
  `citation_precision` is necessary but not sufficient for "the answer is
  accurate" - citing a real source while misquoting its content should not
  be reported as a success by this metric alone, and the write-up
  shouldn't imply otherwise.

### 3. Once real transcripts exist (post-`make eval-live`)

- Spot-check several real transcripts: for every specific number, file
  path, or quote in the final answer, confirm a tool result in that same
  conversation actually contains it. Flag any claim that doesn't.
- Check whether `tool_errors` (a tool that failed) ever gets silently
  dropped from the final answer rather than causing the agent to say "I
  couldn't verify X" - an agent that answers confidently despite a visible
  tool failure in its own transcript is a real finding.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Regex correctness | Extracts real citation formats correctly | Truncates or mismatches on real path shapes |
| Evidence pool completeness | All tool results included, not just one tool's | `get_file`-sourced citations wrongly flagged unsupported |
| Vacuous-pass honesty | "No citations attempted" tracked separately from "fully grounded" | Both silently collapse into the same 1.0 |
| Claim-level accuracy | README distinguishes "cited correctly" from "is true" | Citation precision presented as a full accuracy guarantee |

## Red Flags

- A real transcript where the final answer states a specific number that
  doesn't appear in any tool result in that conversation.
- A tool error in the transcript that the final answer doesn't acknowledge.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "citation_precision is 1.0, so the answer is accurate" | citation_precision only checks that cited *paths* were actually retrieved - it says nothing about whether the stated facts about them are correct. |
| "No citations means nothing to hallucinate" | True for this metric specifically, but a pattern of zero-citation answers on questions that should need evidence is itself worth flagging, just via a different signal. |

## Output Format

Report findings as Critical / Important / Minor with file:line references
(or transcript excerpts, once real ones exist) and a concrete suggested
fix. List explicit passes.
