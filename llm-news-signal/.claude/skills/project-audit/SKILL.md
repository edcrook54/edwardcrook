---
name: project-audit
description: Use when llm-news-signal has real extraction results (not PENDING) and needs an independent, multi-lens audit before being called done - triggers on "final review", "audit this project", "review before shipping", "check this analysis", "pre-ship review".
---

# Project Audit

## Overview

This is the orchestrator for this project's five domain checkers
(`label-reliability-checker`, `lopez-de-prado-checker` (reused verbatim
from `crypto-cointegration-signal`), `multiple-comparison-checker`,
`llm-determinism-checker`, `narrative-checker`) - one more than the sibling
projects' usual four, because this project's dependency on an external LLM
call introduces a reproducibility risk (`llm-determinism-checker`) that the
others don't have. Same dispatch-and-synthesize pattern otherwise:
independently-briefed reviewers, each with a narrow lens and none of them
carrying the builder's assumptions, run in parallel and only synthesized
after all have reported back.

## When to Use

**Not yet applicable at the time this project was built** - `make extract`
requires a real `ANTHROPIC_API_KEY` that wasn't available, so
`data/extractions.json` doesn't exist and the README's headline section is
marked PENDING. Run this skill only once a real extraction and analysis run
has happened and the README reflects real numbers - auditing placeholder/
pending results would produce meaningless findings.

## Process

### 1. Confirm the project is actually ready to audit

Confirm: `make lint && make typecheck && make test` all pass, `make extract`
has been run with a real API key (not the test fixtures), `make reliability`
and `make analyze` both ran against that real `data/extractions.json`, and
the README's headline section has been updated with real numbers (the
PENDING markers removed).

### 2. Dispatch all five checkers in parallel, each scoped narrowly

Give each checker a self-contained brief with exactly the files its lens
needs:

- `label-reliability-checker`: `data/reliability_labels.json`,
  `data/extractions.json`, `scripts/build_reliability_labels.py`,
  `src/llmsignal/reliability/`, `tests/test_reliability.py`.
- `lopez-de-prado-checker`: `src/llmsignal/backtest.py`,
  `src/llmsignal/returns/bars.py`, `src/llmsignal/stats/ic.py`, the README's
  headline/backtest sections.
- `multiple-comparison-checker`: `src/llmsignal/analyze.py`,
  `src/llmsignal/stats/ic.py`, `tests/test_stats.py`, the README's headline
  section.
- `llm-determinism-checker`: `src/llmsignal/extraction/client.py`,
  `src/llmsignal/extract.py`, `tests/test_extraction.py`.
- `narrative-checker`: `README.md`, `CLAUDE.md`,
  `data/analysis_results.json`.

Issue all five dispatches in the same turn so they run concurrently.

### 3. Collect findings independently, then synthesize

Same rules as the sibling projects: cross-reference convergent findings
before deduplicating, re-rank by combined severity, keep every checker's
explicit passes, write the synthesis as a standalone `AUDIT.md`.

### 4. Act on it deliberately

Fix what's cheap and clearly correct. Anything that would change a reported
headline number or require redesigning a component is a recommendation for
the project owner to decide on, not an auto-apply.

## Output Format

`AUDIT.md`, structured as: one paragraph on what was audited and when, then
Critical / Important / Minor sections (each finding with its source
checker(s), file/line, suggested fix), then a closing "Verified sound" list.
