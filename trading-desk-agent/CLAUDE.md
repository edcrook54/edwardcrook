# Project brief for Claude Code

## what this is

Core AI/Agents track piece — sits with `trading-research-rag` (SWE) and
`llm-news-signal` (DS). A tool-using agent over the sibling quant projects,
plus a multi-agent audit-dispatch mode that productionizes `project-audit`
as live running code instead of static Claude Code instructions.

## rules, don't relitigate

- **No fabricated agent results.** No key at build time -> README live-eval
  is PENDING. Everything else runs against real tools + real data with a
  *scripted* client — never present that as a real model decision.
- **Tool-use safety is structural, not advisory.** Allowlists/path checks
  enforced in code, not docstrings. Every tool call wrapped so an exception
  becomes a visible `tool_result` error, never a crash or silent empty result.
- **Audit-dispatch synthesis's limits are disclosed.** Convergence detection
  is keyword-overlap (Jaccard), not semantic understanding — say so.
- **Citations must be checkable.** `citation_precision` exists to catch a
  claim about a file/path never actually retrieved via a tool that run.

## facts, don't relitigate

- `rerun_backtest_variant` shells out to `pm-bayes-pricer`'s real CLI using
  *that project's* venv, needs its bars data locally (see
  `llm-news-signal/CLAUDE.md` for why that's gitignored, not committed).
- `search_corpus` needs `trading-research-rag`'s `/search` running
  (`make serve` there) — no reimplemented retrieval.
- installed anthropic SDK has no `temperature` param (same fact as
  `llm-news-signal`). Doesn't matter here — an agent reasoning differently
  per context is fine, this isn't a labeling pipeline.
- `agent/audit_dispatch.py`'s dispatch/synthesize functions are real and
  reusable, not a demo. If this project's own AUDIT.md ever gets
  regenerated with a real key, use this module to do it.

## architecture (implemented, don't redesign)

1. raw Anthropic tool-use loop (`agent/loop.py`), bounded iterations,
   injectable client/settings/registry for testing
2. 4 sandboxed tools (`tools/`), independently testable
3. `rerun_backtest_variant` allowlist excludes anything redefining the
   train/test boundary
4. async multi-checker dispatch via `asyncio.gather`, never sequential —
   the whole point is independence
5. eval metrics limited to what's mechanically checkable without an LLM
   judge (citation precision, tool-usage recall, keyword recall)

## checking it works

`make install && make test && make lint && make typecheck`
(optional: `make serve` in trading-research-rag/ for search_corpus)
`make eval-live` (needs key) = the real result

## non-goals

- no arbitrary code execution — tools are fixed, narrow dispatch, never eval/exec
- no Docker/live-service packaging before the agent-quality question is answered
- no LLM-as-judge without validating it against human labels first — an
  unvalidated judge grading an agent is a known failure mode

## final gate

Once `make eval-live` ran for real: `project-audit` skill, checkers =
`tool-use-safety`, `hallucination-citation`, `agent-eval-validity`, `narrative`.
