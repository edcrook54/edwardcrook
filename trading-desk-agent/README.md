# trading-desk-agent

A tool-using agent over this repo's own quant projects. It answers questions
by actually calling real tools (retrieval, stat tests, a sandboxed backtest
re-run, restricted file reads) and cites exactly where every claim came from.
Also has a live multi-agent audit-dispatch mode that productionizes this
repo's own `project-audit` pattern as real code. Raw Anthropic API, no
framework.

## ⚠ live-agent result: PENDING

Agent loop and audit-dispatch both need real API calls (the whole point is
the model deciding things), and this environment had none. **No key
committed here either, don't want some rando burning my Anthropic credits
lol.** Everything below runs against a scripted client instead, and says so.
Run `make eval-live` with your own key for the real result.

## try it (no key needed, 3 of 4 tools are fully real)

```python
from deskagent.tools.run_stat_test import run_stat_test
run_stat_test("adf", [0.01, -0.02, 0.015, ...])  # real statsmodels ADF test

from deskagent.tools.rerun_backtest_variant import rerun_backtest_variant
rerun_backtest_variant("SOL", overrides={"anchor_step_hours": 48})
# -> real subprocess call into pm-bayes-pricer's actual backtest CLI,
#    real cached bars, real numbers back. not a stub.

from deskagent.tools.get_file import get_file
get_file("pm-bayes-pricer/README.md")  # restricted, real file read
```

`search_corpus` is the 4th tool. Needs `trading-research-rag` running
(`make serve` there), also no LLM.

## scope

- all 4 tools tested for real, no key needed (incl. the real pm-bayes-pricer
  subprocess call, a mocked HTTP round-trip for search_corpus)
- agent loop's control flow (iteration cap, tool errors, transcripts) tested
  against a scripted client
- audit-dispatch's concurrency is real (verified by timing, not claimed).
  Its "convergence detection" is just keyword overlap (Jaccard), not real
  understanding, said plainly here rather than oversold
- not tested: does the agent actually reason well with a real model deciding
  things (needs a key); true task-success grading (needs an LLM judge,
  validated against human labels first, not built yet, on purpose)
- 16 gold eval questions, not 30-50: a smaller, hand-curated set
- `rerun_backtest_variant` can't touch the train/test boundary, only
  hyperparameters
- no defense against prompt injection from tool output yet. Tool output goes
  straight into the next model message untagged. Low risk here (fixed,
  trusted file set) but a real gap for any tool-using agent, flagged plainly
- subprocess timeout bounds wall-clock time, no guarantee it cleans up a full
  process tree

## bugs the audit caught

- citation-precision regex ate trailing punctuation, so a correctly-cited
  source at the end of a sentence got falsely flagged as hallucinated. Fixed.
- matching was a raw substring check, so a truncated/mangled citation could
  pass as "supported." Fixed, matches whole tokens now.
- 8 of 16 gold questions expected `search_corpus` to find stuff it was never
  indexed to reach (trading-research-rag only indexes 2 of the 4 sibling
  projects). Fixed, routed to `get_file` instead where that's the only tool
  that can actually reach it.

Full writeup in `AUDIT.md`.

## how it works

```
question -> AgentLoop -> model picks a tool (needs key) -> dispatch
  -> search_corpus | run_stat_test | rerun_backtest_variant | get_file
  -> result fed back -> loop (bounded iterations) -> answer + transcript

separately: N CheckerBriefs -> asyncio.gather(checkers) -> synthesize()
```

## run it

```bash
cp .env.example .env   # set your own key
make install && make test && make lint && make typecheck
# optional: make serve in trading-research-rag/ for search_corpus
make eval-live          # the real result, needs a real key
```

## why

- raw Anthropic API, no framework: the whole loop fits in one file and is
  easy to read
- settings/client injectable everywhere, which is what makes it testable
  without a live key or service
- `rerun_backtest_variant` shells out to the real CLI instead of importing
  internals, same "vendor, don't cross-import" rule as the other projects

## not done

the real `make eval-live` run and every number downstream; a live
audit-dispatch run against real checker prompts; an LLM-as-judge (needs
validation against human labels first); Docker/live-service packaging
(scoped out on purpose, CLI+API is enough for now); full audit against real
numbers (pre-execution audit already done, see `AUDIT.md`).
