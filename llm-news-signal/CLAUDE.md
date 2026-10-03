# Project brief for Claude Code

## what this is

DS-track piece: does an LLM-extracted hawkish/dovish score from real FOMC
statements predict BTC/ETH forward returns. LLM is a feature extractor here,
not an agent — deliverable is the stats.

## rules, don't relitigate

- **LLM is a noisy labeler.** Validate it (kappa, Pearson) before trusting any
  downstream stat, same as any other labeling source.
- **No fabricated results.** No `ANTHROPIC_API_KEY` at build time ->
  `data/extractions.json` doesn't exist -> README headline stays PENDING.
  Don't invent numbers, don't drop the PENDING label without real numbers to
  replace it.
- **Gold labels never come from the system's own output.** All 38 hand labels
  written from the raw statements, before any extraction existed.
- **Multiple comparisons disclosed, not hidden.** 6 tests (2 assets x 3
  horizons), Benjamini-Hochberg across all of them, uncorrected count shown too.
- **Honest > impressive.** Non-significant IC after correction is the finding,
  not a footnote.
- **Reliability gate is enforced, not advisory.** `analyze.py` calls
  `run_reliability_check` itself, refuses below `KAPPA_THRESHOLD` (0.4). Don't
  remove that call "to just see the numbers."

## facts, don't relitigate

- `data/fomc_statements.json`: 38 real statements, Jan 2022–Sep 2026, verbatim
  from federalreserve.gov. Min gap 41 days > longest horizon (168h) — no
  overlap between events.
- Price data: `pm-bayes-pricer/data/bars/{XBT,ETH}_1m.parquet`. 6 of 38
  meetings fall past the bars' cutoff, correctly excluded (`None`, not
  truncated).
- **That bars data is gitignored in pm-bayes-pricer, not committed anywhere.**
  `make test/lint/typecheck` don't need it and pass on a fresh clone; only
  `make analyze` does, and needs `pm-bayes-pricer`'s own `make bars` run
  first. Don't "fix" by committing ~180MB of parquet.
- Installed `anthropic` SDK has **no `temperature` param** (removed upstream).
  Determinism = response caching, not a sampling knob. A test pins this —
  don't re-add `temperature=` blindly.
- pm-bayes-pricer bars are left-labeled (`ts==T` covers `[T, T+60s)`). FOMC
  releases land on exact minutes, so "before" price MUST use strict `<`, never
  `<=` — audit caught this as a real look-ahead bug affecting all 38 events.

## architecture (implemented, don't redesign)

1. tool-forced extraction, validated against pydantic schema (`extraction/`)
2. response cache keyed on `(model, prompt_version, text)` = the determinism
3. `WalkForwardSplitter` vendored from `crypto-cointegration-signal`
4. single-asset backtest with flat per-event round-trip cost — NOT
   crypto-cointegration-signal's turnover-diff `CostModel` (that assumes a
   continuously-held position; these are independent bets, audit caught this)
5. Spearman rank-IC + Newey-West + Benjamini-Hochberg across all 6 tests

## checking it works

`make install && make test && make lint && make typecheck`, then
`make extract` (needs key) -> `make reliability` -> `make analyze` (real result)

## non-goals

- no real-time Fed-funds-futures data for `surprise_magnitude` — disclosed
  heuristic instead, not a TODO
- no swapping LLM provider to dodge the missing key — point is validating
  Claude specifically
- no backfilling price data past the bars cutoff — excluding honestly is correct

## final gate

Once `make extract` ran for real: `project-audit` skill, checkers =
`label-reliability`, `lopez-de-prado` (verbatim reuse), `multiple-comparison`,
`llm-determinism`, `narrative`.
