# trading-desk-agent

**A tool-using research-desk agent over this repo's own quant projects — answers
open-ended questions by actually calling real tools (retrieval, statistical tests, a
sandboxed backtest re-run, restricted file reads) and cites exactly where every claim
came from. Includes a live multi-agent audit-dispatch mode that productionizes this
repo's own `project-audit` skill as real orchestrated code.**

Built on the raw Anthropic API (`client.messages.create`), not a framework — same
house style as the rest of this repo.

## ⚠ Live-agent eval result: PENDING

Both the agent loop and the audit-dispatch mode need real `ANTHROPIC_API_KEY` calls
(the whole point is the model deciding which tools to call), and this environment
had none. **Every number below is from a scripted/mocked client, not a real agent
run** — the full mechanism (4 real tools, the bounded tool-use loop, the async
multi-checker dispatch, and the eval metrics) is built, tested, and verified against
real sibling-project data wherever that doesn't require an LLM call, but the actual
"does the agent answer well" result does not exist yet. Run `make eval-live`
yourself with a real key to produce it.

## See the results (2 minutes, nothing to install)

```
$ make test
...41 passed

$ python -c "..." # real tool, no API key needed - see below
```

Three of the four tools need no LLM at all and are fully real right now:

```python
from deskagent.tools.run_stat_test import run_stat_test

run_stat_test("adf", [0.01, -0.02, 0.015, ...])  # a real statsmodels ADF test

from deskagent.tools.rerun_backtest_variant import rerun_backtest_variant

rerun_backtest_variant("SOL", overrides={"anchor_step_hours": 48})
# -> {'asset': 'SOL', 'n_contracts': 4380, 'log_loss_by_model': {'gbm_har': 0.342, ...}}
# a REAL subprocess call to pm-bayes-pricer's actual backtest CLI against its
# real cached bars - not a stub.

from deskagent.tools.get_file import get_file

get_file("pm-bayes-pricer/README.md")  # a real, restricted file read
```

`search_corpus` is the fourth tool and the only one with an external dependency: it
needs `trading-research-rag`'s service running (`make serve` there) — also no LLM
required, pure retrieval.

## Scope and limits

* **Tested for real, no API key needed:** all four tools (including a genuine
  subprocess call to `pm-bayes-pricer`'s real backtest CLI against its real cached
  bars, and a genuine HTTP round-trip to a mocked `trading-research-rag` service);
  the bounded tool-use loop's control flow (iteration cap, tool-error handling,
  transcript logging) against a scripted fake Anthropic client; the async
  multi-checker dispatch's genuine concurrency (verified by timing, not asserted)
  and its keyword-overlap convergence detection; all three eval metrics
  (citation precision, tool-usage recall, keyword recall) against hand-worked
  transcripts.
* **Not yet tested:** whether the agent actually reasons well and calls the right
  tools when a real model is making the decisions (needs `ANTHROPIC_API_KEY`);
  whether the multi-agent audit-dispatch mode produces genuinely useful findings
  against real checker prompts (same reason); true task-success grading, which
  would need an LLM-as-judge validated against held-out human judgments — itself
  another live-API dependency, deliberately not faked with a mechanical substitute
  dressed up as semantic grading.
* **The audit-dispatch synthesis's "convergence detection" is a keyword-overlap
  heuristic (Jaccard similarity over word sets), not semantic understanding.** It
  will miss two checkers describing the same root cause in genuinely different
  words, and could in principle flag two unrelated findings that happen to share
  vocabulary. This is honestly weaker than the judgment a human (or Claude Code)
  applies when running this same pattern manually — stated plainly here, not just
  in "Design decisions" below.
* **16 gold eval questions** (`config/eval_questions.json`), not the 30-50 a fuller
  eval might use — a smaller, hand-curated set covering retrieval, audit-history,
  quant-results, direct tool computation, cross-project reasoning, and an explicit
  refusal case (asking for live Bitcoin price, which no tool here provides).
* **`rerun_backtest_variant` cannot redefine the train/test boundary.** Only
  hyperparameters (`z_grid`, `ewma_half_life_days`, `horizons_days`, etc.) are
  overridable; `start`/`first_test_year`/`end_year`/`asset` are fixed by the base
  config — the agent can ask "what if the vol half-life were shorter," not "what if
  the test window were different."
* **No prompt-injection-from-tool-output mitigation exists yet.** Tool results
  (e.g. a file's contents via `get_file`) go straight into the next message sent
  back to the model with no framing marking them as untrusted data. For the
  current, fixed set of trusted sibling-project files this is a low-risk gap, but
  it's a real one for any tool-use agent that reads external content, and it's
  disclosed here rather than silently left unmentioned — found during this
  project's own audit (see AUDIT.md).
* **A subprocess timeout bounds wall-clock time, not necessarily the full process
  tree or resource usage.** `rerun_backtest_variant`'s `subprocess.run(timeout=...)`
  kills the direct child on timeout; if it ever spawned grandchild processes, those
  aren't guaranteed to be cleaned up. Not currently exploitable (the wrapped CLI
  doesn't fork further), but noted as a limitation, not a guarantee.

## What's actually been verified

* **A real subprocess integration, not a stub**: `rerun_backtest_variant` genuinely
  shells out to `pm-bayes-pricer`'s `python -m pmq.crypto.backtest` with a merged,
  whitelisted config, against the real cached SOL bars, and computes real log-loss
  numbers from the real output parquet.
* **Genuine concurrency in the audit dispatch**, not just claimed: three 0.05s-delay
  scripted checker calls complete in well under 0.15s total when dispatched via
  `asyncio.gather`, confirmed by timing the test, not by reading the code and
  assuming.
* **Citation precision actually catches hallucination**: a scripted answer that
  cites one real, retrieved file plus one fabricated path is correctly flagged with
  precision 0.5, not 1.0, with the fabricated path listed under `unsupported`
  (`tests/test_eval_metrics.py::test_citation_precision_flags_a_hallucinated_citation`);
  a separate case with *only* a fabricated citation correctly scores 0.0
  (`test_citation_precision_is_zero_when_every_citation_is_unsupported`). The
  project's own audit caught an earlier version of this metric where a citation
  immediately followed by a sentence-ending period (e.g. "...see
  `pm-bayes-pricer/README.md`.") was wrongly flagged as unsupported — the trailing
  `.` got swept into the extracted token. Fixed; see AUDIT.md.
* **The agent loop never crashes on a bad tool call**: an unknown tool name or a
  tool that raises both become a visible `tool_result` with `is_error: true` that
  the loop continues past, not an unhandled exception.
* **`get_file` genuinely cannot escape its allowed roots**: path traversal
  (`../../etc/passwd`-style) and roots outside the allowlist are both rejected,
  tested against the real filesystem, not a mocked one.

## Architecture

```
question -> AgentLoop.run()
              |
              v
   client.messages.create(tools=[4 schemas])  <-- ANTHROPIC_API_KEY required
              |                                   (PENDING in this build)
      tool_use? --no--> final answer, transcript written
              |yes
              v
   dispatch -> search_corpus | run_stat_test | rerun_backtest_variant | get_file
              |
              v
   tool_result appended -> loop (bounded by max_iterations)


Separately: multi-agent audit-dispatch mode
   N CheckerBriefs -> asyncio.gather(run_checker x N)  <-- ANTHROPIC_API_KEY required
                            |
                            v
                   synthesize() -> cross-referenced, severity-ranked SynthesizedAudit
```

## Quick start

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY
make install
make test && make lint && make typecheck
# (optional) in trading-research-rag/: make serve   - needed for search_corpus
make eval-live          # the real headline result - requires a real API key
```

## Layout

| Path | Purpose |
|---|---|
| `src/deskagent/tools/` | The four sandboxed tools: `search_corpus.py`, `run_stat_test.py`, `rerun_backtest_variant.py`, `get_file.py` |
| `src/deskagent/agent/loop.py` | The bounded tool-use agent loop (`AgentLoop`) |
| `src/deskagent/agent/audit_dispatch.py` | Live multi-agent audit dispatch + keyword-overlap synthesis |
| `src/deskagent/agent/schemas.py` | The four tools' Anthropic tool-use schemas |
| `src/deskagent/eval/` | `metrics.py` (citation precision, tool-usage recall, keyword recall), `run_eval.py` (`make eval-live`) |
| `config/eval_questions.json` | 16 hand-written gold questions with expected tools/keywords/citations |
| `tests/` | 41 tests: real tool integration tests (incl. a genuine `pm-bayes-pricer` subprocess run), scripted-client agent-loop tests, async-concurrency-timed dispatch tests, hand-worked metric examples |

## Design decisions

* **Raw Anthropic API, no agent framework.** The whole control flow fits in
  `agent/loop.py` in well under 200 lines and is fully inspectable — consistent
  with this repo's "derive from scratch" house style.
* **Settings are injectable everywhere**, not just read from a global — every tool
  and `AgentLoop` itself accept an optional `settings`/`client` override, which is
  what makes the whole mechanism testable without any live service or API key.
* **Audit-dispatch synthesis is a keyword-overlap heuristic, disclosed as one.**
  Detecting that two checkers converged on the same root cause uses Jaccard
  similarity over their free-text descriptions' word sets — simple, inspectable, and
  honestly weaker than the semantic judgment a human (or Claude Code) applies when
  running this same pattern manually, which is exactly what this project is
  attempting to productionize. Documented as a stated limitation, not a hidden one.
* **`rerun_backtest_variant` wraps the real CLI, not an internal import.** Calling
  `pm-bayes-pricer`'s actual `python -m pmq.crypto.backtest` as a subprocess, rather
  than importing its internal modules, matches the "vendor, don't cross-import"
  rule the other sibling projects already established, applied here as "shell out
  to the real entrypoint" instead.

## Not yet done

The actual `make eval-live` run (needs `ANTHROPIC_API_KEY`) and therefore every real
agent-quality number; a live run of the multi-agent audit-dispatch mode against a
real checker prompt set; an LLM-as-judge for true task-success grading, validated
against held-out human judgments; Docker/live-service packaging (explicitly scoped
out in favor of CLI+API-only, per the build plan — a stretch goal, not a gap); the
project-audit skill's full run against real numbers (deliberately deferred, same
reasoning as `llm-news-signal` — a pre-execution pipeline audit has already been run,
see `AUDIT.md`).
