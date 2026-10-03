# Project brief for Claude Code

## What this is

A portfolio project demonstrating data-science rigor applied to an LLM
extraction pipeline — DS-track evidence for AI Engineer roles (e.g. Oliver
Wyman's Quotient AI / WAVE team), sitting alongside `crypto-cointegration-signal`,
`pm-bayes-pricer`, and `trading-research-rag`. The LLM is a feature
extractor here, not an agent — the deliverable is the statistics, not the
chatbot. Question: does an LLM-extracted hawkish/dovish score from real FOMC
statement text carry predictive power for BTC/ETH forward returns?

## Non-negotiable values

- **The LLM is a noisy labeler, validated like any other.** Its extraction
  reliability against independent human labels (Cohen's kappa, Pearson
  correlation) must be reported before any downstream statistical claim is
  trusted, exactly as `crypto-cointegration-signal` validates its own inputs.
- **No fabricated results.** As of this writing, `data/extractions.json`
  does not exist because no `ANTHROPIC_API_KEY` was available when this
  project was built. Every number in the README's headline section is
  marked PENDING until `make extract` has actually run against the real API
  — don't invent placeholder numbers and don't quietly drop the PENDING
  label once a real run happens without replacing it with real numbers.
- **Gold/reliability labels never come from the system's own output.** All
  38 hand labels in `data/reliability_labels.json` were written by reading
  `data/fomc_statements.json` directly (see `scripts/build_reliability_labels.py`),
  before any LLM extraction existed to anchor on.
- **Multiple comparisons are disclosed, not hidden.** Six tests are run
  (2 assets x 3 horizons); Benjamini-Hochberg correction is applied across
  all six, and the uncorrected count is shown alongside the corrected one.
- **Honesty over impressiveness**: if the IC isn't significant after
  correction, that's the headline finding, not a footnote.
- **The reliability gate is enforced, not advisory.** `analyze.py` calls
  `run_reliability_check` itself and refuses to proceed if kappa doesn't
  clear `KAPPA_THRESHOLD` (0.4) - don't remove that call to "just see the
  numbers anyway"; a separate `make reliability` target that someone could
  forget to run isn't a gate.

## Data specifics (don't relitigate these)

- `data/fomc_statements.json`: 38 real FOMC statements, Jan 2022 - Sep 2026,
  compiled from federalreserve.gov press releases (verbatim excerpts, not
  paraphrased). Minimum gap between meetings is 41 days — comfortably more
  than the longest horizon tested (168h/7 days), so forward-return windows
  for consecutive meetings never overlap.
- Price data: `pm-bayes-pricer/data/bars/{XBT,ETH}_1m.parquet` (real, cached
  1-minute bars, 2013/2015-2025). 6 of the 38 meetings (the most recent 2026
  ones) fall after the bars' 2025-12-31 cutoff and are correctly excluded
  from the price-joined analysis (`forward_return` returns `None`, not a
  truncated/wrong value) - don't "fix" this by extending the horizon logic,
  the data genuinely doesn't exist yet.
- **`pm-bayes-pricer/data/bars/*.parquet` is gitignored in that project and
  is NOT committed anywhere** - confirmed by checking its `.gitignore` and by
  the fact `make analyze` fails with a plain `FileNotFoundError` when run
  against a fresh clone of this repo. It only exists in this machine's local
  working copy. Don't "fix" this by committing ~180MB of parquet files into
  git without being asked - that's a real, deliberate repo-size decision, not
  a bug. `make test`/`lint`/`typecheck` never touch this data and pass on a
  fresh clone regardless; only `make analyze` needs it, and needs it to be
  regenerated locally first (`pm-bayes-pricer`'s own `make bars` target, which
  itself needs the raw Kraken tick CSVs - see that project's README/setup.md).
- `event_time_et_to_utc` must handle both EST and EDT correctly (release is
  always 2pm ET, but that's a different UTC offset depending on the date) -
  this is tested against both a January and a June date deliberately.
- `anthropic`'s `messages.create` in the SDK version this was built against
  has **no `temperature` parameter** - it was removed from the public API.
  Determinism rests entirely on response caching (`recorded_responses_path`),
  not a sampling-randomness knob. Don't add `temperature=` back in without
  checking the installed SDK version first (`test_anthropic_sdk_still_has_no_temperature_parameter`
  in `tests/test_extraction.py` will fail loudly if a future SDK reintroduces it).
- `pm-bayes-pricer`'s cached bars are **left-labeled**: the row with `ts==T`
  spans `[T, T+60s)`, so its `close` reflects trading up to 59s *after* `T`.
  Every FOMC release time lands exactly on a minute boundary, so
  `forward_return`'s "before" price MUST use a strict `<` cutoff
  (`_price_strictly_before`), never `<=` - using `<=` here was a real
  look-ahead bug the audit caught (see AUDIT.md), affecting all 38 events,
  not an edge case.

## Architecture decisions already made (implement, don't redesign)

1. Tool-forced extraction via `EXTRACTION_TOOL_SCHEMA`, validated against
   the `ExtractionResult` pydantic model (`src/llmsignal/extraction/`)
2. Response caching keyed on `(model, prompt_version, text)`
   (`extraction/client.py`) - the determinism/reproducibility mechanism
3. `WalkForwardSplitter` vendored (not imported) from `crypto-cointegration-signal`
4. Single-asset directional backtest (`backtest.py`) with a flat per-event
   round-trip cost, NOT a turnover-diff cost model - deliberately NOT
   reusing `crypto-cointegration-signal`'s `BacktestEngine`/`CostModel`,
   which assume a pairs spread / continuously-sampled position series
   (see `backtest.py`'s module docstring - this project's first draft got
   this wrong and the audit caught it, see AUDIT.md)
5. Spearman rank-IC with Newey-West HAC t-stats, Benjamini-Hochberg across
   all 6 (asset x horizon) tests (`stats/ic.py`)

## Checking the pipeline

1. `make install`
2. `make test && make lint && make typecheck`
3. `make extract` (needs `ANTHROPIC_API_KEY`) — writes `data/extractions.json`
4. `make reliability` — kappa/correlation against `data/reliability_labels.json`
5. `make analyze` — the real headline result; writes `data/analysis_results.json`

## Explicit non-goals

- Don't try to source real-time market-implied probabilities (Fed funds
  futures) to ground `surprise_magnitude` precisely - the hand labels use a
  disclosed regime-transition heuristic instead (see README "Scope and
  limits"). This is a stated limitation, not a TODO to silently fix by
  fabricating a data source.
- Don't swap in a different LLM provider to work around the missing API key
  - the point is validating Claude as a labeler, and a different model
  wasn't what the reliability labels were calibrated against.
- Don't backfill BTC/ETH price data for the 6 meetings past the bars'
  cutoff - excluding them honestly is correct, not a gap to paper over.

## Final review gate (skills-based audit)

Once `make extract` has actually run with a real key and the README's
headline section has real numbers (not PENDING), run the `project-audit`
skill (`.claude/skills/project-audit/`) before calling this done - checkers:
`label-reliability-checker`, `lopez-de-prado-checker` (reused verbatim from
`crypto-cointegration-signal`), `multiple-comparison-checker`,
`llm-determinism-checker`, and `narrative-checker`.
