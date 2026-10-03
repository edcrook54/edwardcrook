# Project brief for Claude Code

## What this is

A portfolio project demonstrating Core AI/Agents engineering — the third
showcase project (Core AI/Agents track), sitting alongside
`trading-research-rag` (SWE track) and `llm-news-signal` (DS track). A
tool-using agent over this repo's own quant projects, plus a multi-agent
audit-dispatch mode that productionizes the `project-audit` pattern used
across every sibling project as live, running code instead of static
Claude Code instructions.

## Non-negotiable values

- **No fabricated agent-quality results.** No `ANTHROPIC_API_KEY` was
  available when this was built, so the README's live-eval section is
  marked PENDING. Everything demonstrated instead runs against real tools
  and real data with a *scripted* client - never present a scripted
  transcript as if it were a genuine model decision.
- **Tool-use safety is structural, not advisory.** `rerun_backtest_variant`
  enforces its override allowlist in code (raises on anything outside it),
  not just in a docstring; `get_file` enforces its path allowlist and size
  cap in code; every tool call in the agent loop is wrapped so a raised
  exception becomes a visible `tool_result` error, never an unhandled
  crash or a silent empty result.
- **The audit-dispatch synthesis's limitations are disclosed, not hidden.**
  Convergence detection is a keyword-overlap heuristic (Jaccard similarity),
  not semantic understanding - say so in the README, don't imply it's
  smarter than it is.
- **Citations must be checkable, not just plausible-looking.** The eval's
  `citation_precision` metric exists specifically to catch an answer that
  names a file/path it never actually retrieved via a tool in that
  conversation.

## Data specifics (don't relitigate these)

- `rerun_backtest_variant` shells out to `pm-bayes-pricer`'s real
  `python -m pmq.crypto.backtest` CLI using *that project's own venv*
  (`pm-bayes-pricer/.venv/bin/python`), not this project's. It needs
  `pm-bayes-pricer/data/bars/{XBT,ETH,SOL}_1m.parquet` to exist locally (see
  `llm-news-signal/CLAUDE.md` for why that data isn't committed to the repo).
- `search_corpus` is a hard dependency on `trading-research-rag`'s live
  `/search` endpoint (`make serve` there) - it does not reimplement
  retrieval, and raises a clear error naming the fix if the service isn't
  reachable.
- The `anthropic` SDK installed here has no `temperature` parameter (same
  SDK-version fact as `llm-news-signal` - see that project's CLAUDE.md).
  The agent loop doesn't need determinism the way a labeling pipeline does
  (a real agent *should* reason differently given different context), so
  this doesn't block anything here, but don't add `temperature=` to
  `client.messages.create` calls expecting it to work.
- `CheckerBrief`/`CheckerFinding`/`dispatch_checkers`/`synthesize` in
  `agent/audit_dispatch.py` are a real, reusable implementation of this
  repo's `project-audit` pattern - not a demo. If this project's own
  AUDIT.md is ever regenerated with a real key, consider using this
  module to do it, rather than falling back to manual subagent dispatch.

## Architecture decisions already made (implement, don't redesign)

1. Raw Anthropic tool-use loop (`agent/loop.py`), bounded by
   `settings.max_iterations`, with injectable `client`/`settings`/
   `tool_registry` for testability
2. Four sandboxed tools (`tools/`), each independently testable without
   the others
3. `rerun_backtest_variant`'s override allowlist excludes anything that
   redefines the train/test boundary (`start`, `first_test_year`,
   `end_year`, `asset` are fixed by the base config)
4. Async multi-checker dispatch via `asyncio.gather` (`agent/audit_dispatch.py`),
   never sequential awaits - the whole point of the pattern is independence
5. Eval metrics (`eval/metrics.py`) limited to what's mechanically checkable
   without an LLM judge: citation precision, tool-usage recall, keyword
   recall - true semantic task-success grading is explicitly out of scope
   until a real LLM-as-judge is built and validated

## Checking the pipeline

1. `make install`
2. `make test && make lint && make typecheck`
3. (optional, for `search_corpus`) `make serve` in `trading-research-rag/`
4. `make eval-live` (needs `ANTHROPIC_API_KEY`) - the real headline result

## Explicit non-goals

- Don't let the agent execute arbitrary code - `rerun_backtest_variant` and
  `run_stat_test` are each a fixed, narrow dispatch over named operations,
  never an `eval`/`exec` path.
- Don't build Docker/live-service packaging before the agent-quality
  question itself is answered with a real key - CLI+API-only is the
  deliberate scope for now.
- Don't build an LLM-as-judge without also validating it against held-out
  human judgments first (same discipline `llm-news-signal` applies to its
  own LLM-as-labeler) - an unvalidated judge grading an agent is a known
  failure mode, not a shortcut worth taking under time pressure.

## Final review gate (skills-based audit)

Once `make eval-live` has actually run with a real key and the README's
live-eval section has real numbers (not PENDING), run the `project-audit`
skill (`.claude/skills/project-audit/`) before calling this done - checkers:
`tool-use-safety-checker`, `hallucination-citation-checker`,
`agent-eval-validity-checker`, and `narrative-checker`.
