---
name: tool-use-safety-checker
description: Use when reviewing an agent's tool-use loop and sandboxed tools for unbounded compute/cost paths, arbitrary code execution, or prompt-injection-from-tool-output risk - triggers on "tool safety", "sandboxed tool", "arbitrary code execution", "unbounded cost", "agent guardrails", "max iterations".
---

# Tool-Use Safety Checker

## Overview

An agent that can call real tools is only as safe as the narrowest point in
its tool surface. This skill checks `trading-desk-agent`'s four tools and
its bounded loop for the concrete failure modes that matter for an agent
with subprocess and HTTP access: unbounded compute, arbitrary code
execution, and tool output that could hijack the agent's own next decision.

## When to Use

Before trusting that the agent loop or any of its tools is safe to run
against real (even if sandboxed) side effects.

## Core Checklist

### 1. No arbitrary code execution path

- Confirm `run_stat_test` and `rerun_backtest_variant` each dispatch over a
  fixed, named set of operations (a `test` enum, a config-override
  allowlist) - neither should contain an `eval`/`exec`/`subprocess.run`
  call whose command or arguments are built from unconstrained model input
  without a whitelist check in between.
- Confirm `rerun_backtest_variant`'s override keys are checked against
  `ALLOWED_OVERRIDE_KEYS` *before* being merged into the config that gets
  written to disk and passed to the subprocess - not after, and not only in
  a docstring.
- Confirm `get_file` rejects path traversal (`..` components) and anything
  outside `allowed_file_roots` by resolving the path and checking
  `is_relative_to`, not by string-prefix matching alone (which a crafted
  path can sometimes defeat).

### 2. Bounded compute and cost

- Confirm the agent loop has a real, enforced `max_iterations` cap
  (`settings.max_iterations`) and that hitting it returns a distinguishable
  result (`hit_max_iterations=True`), not an indistinguishable "normal"
  answer - an eval or a caller needs to know the difference.
- Confirm `rerun_backtest_variant`'s subprocess call has a timeout
  (`settings.tool_timeout_seconds`) and that a timeout raises cleanly
  rather than leaving an orphaned process or hanging the whole agent loop.
- Confirm there's no path where the agent could call `rerun_backtest_variant`
  or `search_corpus` an unbounded number of times within a single
  iteration (one tool call per `tool_use` block is the only shape the loop
  supports - confirm this by reading the dispatch loop, not assuming it).

### 3. Tool-output-as-prompt-injection risk

- Tool results become part of the next message sent back to the model
  (`messages.append({"role": "user", "content": tool_results})`). Confirm
  there's no path where a tool result's content could itself be
  interpreted as a system-level instruction change - e.g. `get_file`
  reading a file that happens to contain text designed to look like a new
  system prompt. This is a real risk category for any tool-use agent that
  reads external/untrusted content; check what, if anything, mitigates it
  here (even "nothing yet, disclosed as a known gap" is an acceptable
  answer - a false claim of mitigation is not).
- Confirm tool errors are surfaced as `is_error: true` tool results (so the
  model can see and reason about a failure) rather than being silently
  swallowed into an empty/default success result that could mislead the
  model into stating something false with apparent confidence.

### 4. Settings/credentials hygiene

- Confirm no tool or the agent loop logs or writes the API key anywhere
  (transcripts, error messages, stdout). Check `_write_transcript` and any
  `RuntimeError`/exception messages specifically.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| No arbitrary execution | Fixed dispatch over named ops only | A tool builds a shell command or `eval`s model-provided text |
| Override allowlist enforced | Checked in code before use | Checked only in a docstring/comment |
| Path traversal blocked | `is_relative_to` on a resolved path | String-prefix check a crafted path can defeat |
| Iteration cap enforced | Real cap, distinguishable max-iterations result | Cap exists but the result looks like a normal answer |
| Subprocess timeout | Enforced, raises cleanly | No timeout, or a timeout that leaves an orphan process |
| Credential hygiene | API key never logged/written anywhere | Key appears in a transcript or error message |

## Red Flags

- Any tool that constructs a subprocess command or file path by directly
  interpolating unescaped model-provided input without a prior allowlist
  check.
- A `max_iterations` cap whose "hit the cap" result is indistinguishable
  from a genuine final answer to a downstream consumer.
- An API key appearing anywhere in a written transcript file.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "The model would never ask for something unsafe" | The whole point of a sandboxed tool is that it doesn't depend on the model's good judgment - a safety property enforced only by the model choosing not to misuse it isn't a safety property. |
| "subprocess.run with a timeout is basically safe" | A timeout bounds wall-clock time, not necessarily resource usage (memory, disk) during that window - note this distinction rather than treating a timeout as a complete guarantee. |

## Output Format

Report findings as Critical / Important / Minor with file:line references
and a concrete suggested fix. List explicit passes.
