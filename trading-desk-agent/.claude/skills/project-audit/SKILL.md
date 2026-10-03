---
name: project-audit
description: Use when trading-desk-agent has real live-agent eval results (not PENDING) and needs an independent, multi-lens audit before being called done - triggers on "final review", "audit this project", "review before shipping", "check this agent", "pre-ship review".
---

# Project Audit

## Overview

This is the orchestrator for this project's four domain checkers
(`tool-use-safety-checker`, `hallucination-citation-checker`,
`agent-eval-validity-checker`, `narrative-checker`). Same dispatch-and-
synthesize pattern as every sibling project: four independently-briefed
reviewers, each with a narrow lens and none of them carrying the builder's
assumptions, run in parallel and only synthesized after all four report
back.

Note the irony worth being honest about: this project *also* contains a
real, reusable implementation of this exact pattern
(`agent/audit_dispatch.py`, `dispatch_checkers`/`synthesize`). Once a real
`ANTHROPIC_API_KEY` is available, consider using that module to actually
run this audit, rather than falling back to manual Claude Code subagent
dispatch - using the thing you built to audit itself is a better
demonstration than not using it.

## When to Use

**Not yet applicable at the time this project was built** - `make eval-live`
requires a real `ANTHROPIC_API_KEY` that wasn't available, so the README's
live-eval section is marked PENDING. Run this skill only once a real
agent-eval run has happened and the README reflects real numbers.

## Process

### 1. Confirm the project is actually ready to audit

Confirm: `make lint && make typecheck && make test` all pass, `make eval-live`
has been run with a real API key, and the README's live-eval section has
been updated with real numbers (PENDING markers removed).

### 2. Dispatch all four checkers in parallel, each scoped narrowly

- `tool-use-safety-checker`: `src/deskagent/tools/`, `src/deskagent/agent/loop.py`,
  `src/deskagent/config.py`.
- `hallucination-citation-checker`: `src/deskagent/eval/metrics.py`, a sample
  of real transcripts from `data/transcripts/`, `data/eval_results.json`.
- `agent-eval-validity-checker`: `config/eval_questions.json`,
  `src/deskagent/eval/run_eval.py`, `data/eval_results.json`.
- `narrative-checker`: `README.md`, `CLAUDE.md`, `data/eval_results.json`.

Issue all four dispatches in the same turn so they run concurrently.

### 3. Collect findings independently, then synthesize

Same rules as every sibling project: cross-reference convergent findings
before deduplicating, re-rank by combined severity, keep every checker's
explicit passes, write the synthesis as a standalone `AUDIT.md`.

### 4. Act on it deliberately

Fix what's cheap and clearly correct. Anything that would change a
reported headline number or require redesigning a component is a
recommendation for the project owner to decide on, not an auto-apply.

## Output Format

`AUDIT.md`, structured as: one paragraph on what was audited and when, then
Critical / Important / Minor sections (each finding with its source
checker(s), file/line, suggested fix), then a closing "Verified sound" list.
