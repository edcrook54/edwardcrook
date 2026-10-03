# llm-news-signal

**Does an LLM-extracted hawkish/dovish score from real FOMC statement text carry
predictive power for BTC/ETH forward returns — tested with the same walk-forward,
cost-adjusted, multiple-comparison-aware rigor as `crypto-cointegration-signal`?**

The LLM is used once, as a feature extractor, not an agent — the deliverable is the
statistics, and the LLM's reliability as a labeler is validated before any of them
are trusted.

## ⚠ Headline result: PENDING

This project needs a live Anthropic API call to extract sentiment from each
statement, and no `ANTHROPIC_API_KEY` was available in the environment this was
built in. **Every number below is a placeholder label, not a result** — the full
pipeline (extraction client, reliability validation, rank-IC/multiple-comparison
testing, cost-adjusted backtest) is built, tested, and verified end-to-end against
real price data using a substitute signal (see "What's actually been verified"
below), but the real headline finding does not exist yet. Run `make extract`
yourself with a real key, then `make reliability` and `make analyze`, to produce it.

## See the results (2 minutes, nothing to install)

There's nothing to see yet in the "headline number" sense — see the PENDING notice
above. What you *can* verify without any API key:

```
$ make test
...33 passed

$ make reliability   # will exit, pointing at `make extract` - this is correct:
no extractions found at .../llm-news-signal/data/extractions.json - run `make extract`
first (requires ANTHROPIC_API_KEY, or a fully-populated recorded-response cache)
```

## Scope and limits

* **Tested (mechanically, end to end):** the full pipeline — FOMC statement
  ingestion, timezone-correct EST/EDT event-time conversion, forward-return
  computation against real cached BTC/ETH 1-minute bars, rank-IC with Newey-West
  HAC, Benjamini-Hochberg correction across all 6 (asset × horizon) tests, the
  cost-adjusted walk-forward backtest — all run against real price data using my
  own hand labels substituted in place of the (not-yet-generated) LLM scores,
  purely as a plumbing smoke test. Those numbers are **not reported here** because
  they're not the real signal; see CLAUDE.md for why faking placeholder headline
  numbers would violate this repo's own rules.
* **Not yet tested:** the actual LLM extraction (needs `ANTHROPIC_API_KEY`), and
  therefore the actual reliability/IC/backtest numbers.
* **Data scope:** 38 real FOMC statements, January 2022 – September 2026, compiled
  verbatim from federalreserve.gov (not paraphrased, not fabricated). This is far
  short of the ~50-100 examples a larger reliability study might use — FOMC
  meetings happen only ~8 times a year, and going back further would mix monetary
  regimes that aren't comparable. To compensate for the smaller N, **all 38** are
  hand-labeled for the reliability check, not a subsample.
* **Price data:** real cached 1-minute BTC/ETH bars (2013/2015–2025, from
  `pm-bayes-pricer`). 6 of the 38 meetings (the most recent 2026 ones) fall after
  the bars' 2025-12-31 cutoff and are correctly excluded from the price-joined
  analysis, not truncated or estimated.
* **`pm-bayes-pricer`'s bar files are not committed to this repo and never will
  be as-is** — confirmed by checking its `.gitignore` (`data/bars/` is explicitly
  excluded) and by actually running `make analyze` against a fresh clone of the
  published repo, where it fails with a plain `FileNotFoundError`. `make
  test`/`lint`/`typecheck` never touch this data and pass regardless; only
  `make extract`/`make analyze` need it, and need it regenerated locally first
  via `pm-bayes-pricer`'s own `make bars` (which itself needs the raw Kraken tick
  CSVs — see that project's README). This is a real, disclosed dependency, not a
  gap papered over by committing ~180MB of parquet files without being asked.
* **`surprise_magnitude` labels use a disclosed heuristic, not market data.** My
  hand labels proxy "surprise" from regime-transition position (first hike/cut
  after a pause scores higher than the Nth consecutive move in an established
  cycle), not real-time Fed-funds-futures-implied probabilities, which I don't have
  a local source for. This is a stated limitation of the reliability baseline
  itself, not something the LLM comparison can fix.

## What's actually been verified

* **No look-ahead in the event/price join**: `forward_return`'s "before" price
  uses a *strict* `<` cutoff (the last fully-completed bar strictly before the
  event), and the "after" price uses `<=` at event+horizon — see "What running it
  against real data caught" below for why the strict cutoff specifically matters.
  `event_time_et_to_utc` is tested against both a January (EST) and a June (EDT)
  date so the UTC conversion is never off by an hour.
* **No overlapping event windows**: the minimum gap between consecutive FOMC
  meetings in the dataset is 41 days, comfortably more than the longest horizon
  tested (168h/7 days) — confirmed by actually computing the gaps, not assumed.
* **Gold/reliability labels are independent of the LLM by construction**: every
  entry in `data/reliability_labels.json` was written by reading
  `data/fomc_statements.json` directly (`scripts/build_reliability_labels.py`),
  before any `data/extractions.json` existed to anchor on.
* **The `anthropic` SDK installed here has no `temperature` parameter** — it was
  removed from the public API, confirmed by inspecting the installed SDK's actual
  call signature (not just trusting a comment), and pinned by a test that fails
  loudly if a future SDK upgrade reintroduces it. Determinism rests entirely on
  response caching (`ExtractionClient`), not a sampling-randomness knob.
* **`make analyze` cannot run on unreliable extractions**: it calls the same
  reliability check as `make reliability` itself and refuses to proceed if Cohen's
  kappa doesn't clear 0.4 (Landis & Koch "moderate" agreement) — a structural gate,
  not a separate step someone could forget to run.

## What running it against real data caught

* **A real look-ahead bug**: the original `forward_return` used an "at or before"
  cutoff for the pre-event price too. `pm-bayes-pricer`'s cached bars are
  left-labeled (the bar at `ts==T` spans `[T, T+60s)`), and every FOMC release
  lands exactly on a minute boundary — so the "before" price was actually the
  event-time bar itself, leaking up to 59 seconds of post-announcement trading
  into the pre-event price for **all 38 events**, not an edge case. Fixed with a
  strict `<` cutoff for the before-price only; regression-tested with a case where
  the event-time bar has an artificially large move that must never appear as the
  "before" price.
* **A real cost-accounting bug**: the first draft reused `crypto-cointegration-signal`'s
  turnover-diff `CostModel`, which assumes a continuously-sampled position series —
  correct for a spread held across adjacent bars, wrong here, where each FOMC
  meeting is an independent bet >=41 days apart. Two consecutive same-sign signals
  would have been charged as one continuously-held position (near-zero cost on the
  second "entry"), silently flattering the backtest. Fixed with an explicit
  round-trip cost (entry + exit) per non-flat row; `CostModel` was removed entirely
  rather than left as a vendored-but-wrong dependency.
* **A reliability check that computed a number but didn't gate anything**: the
  first draft's `make reliability` and `make analyze` were independent targets —
  nothing stopped `make analyze` from reporting a result even with a poor kappa.
  Fixed by making `analyze.py` call the reliability check itself and refuse to
  proceed below the stated threshold.

## Architecture

```
data/fomc_statements.json (38 real statements, verbatim from federalreserve.gov)
            |
            v
ExtractionClient (tool-forced, cached by (model, prompt_version, text))
            |                                   ANTHROPIC_API_KEY required here
            v                                   (PENDING in this build)
data/extractions.json
            |
            v
reliability_check (kappa vs. hand labels)
            |
            v  (analyze calls this itself and refuses to proceed if kappa <= 0.4)
          analyze
(join to pm-bayes-pricer's real BTC/ETH bars -> rank-IC + Newey-West +
 Benjamini-Hochberg -> cost-adjusted walk-forward backtest)
```

## Quick start

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY
make install
make test && make lint && make typecheck
make extract           # requires a real API key - writes data/extractions.json
make reliability       # Cohen's kappa + Pearson r vs. data/reliability_labels.json
make analyze           # the real headline result - rank-IC, BH correction, backtest
```

## Layout

| Path | Purpose |
|---|---|
| `src/llmsignal/extraction/` | `schema.py` (the tool-forced output contract), `client.py` (cached, tool-forced extraction) |
| `src/llmsignal/reliability/` | `kappa.py` — Cohen's kappa + Pearson/MAE/bias against hand labels |
| `src/llmsignal/returns/` | `bars.py` — ET→UTC conversion, no-look-ahead forward returns against real cached bars |
| `src/llmsignal/stats/` | `ic.py` — Spearman rank-IC with Newey-West HAC, Benjamini-Hochberg |
| `src/llmsignal/backtest.py` | Vendored `WalkForwardSplitter`; single-asset directional backtest with an explicit per-event round-trip cost |
| `src/llmsignal/reliability_check.py` | `run_reliability_check` — also called directly by `analyze.py` as an enforced gate |
| `src/llmsignal/extract.py`, `analyze.py` | The other two pipeline entry points (`make extract/analyze`) |
| `data/fomc_statements.json` | 38 real statements (verbatim excerpts + rate decisions) |
| `data/reliability_labels.json` | My own 38 hand labels, independent of any LLM output |
| `scripts/build_reliability_labels.py` | Provenance record for how the hand labels were produced |
| `tests/` | 33 tests: hand-worked kappa/BH/Sharpe/IC/backtest examples, EST/EDT timezone correctness, no-look-ahead forward-return logic (incl. the strict-before-price regression), cache determinism, SDK-temperature-removal pin |

## Design decisions

* **The LLM is a feature extractor, not an agent.** One tool-forced call per
  statement, schema-validated output, nothing agentic — this project's point is
  the statistics discipline around an LLM-derived feature, not agent architecture
  (see `trading-desk-agent` for that).
* **`WalkForwardSplitter` vendored, not imported** from `crypto-cointegration-signal`
  (which isn't an installable package and shouldn't share a live runtime
  dependency with this project). `CostModel` was vendored too in a first draft but
  turned out not to fit this project's discrete, independent-bet structure — see
  "What running it against real data caught".
* **Response caching, not `temperature=0`, for determinism.** The installed
  `anthropic` SDK has no `temperature` parameter; re-running `make extract` on
  unchanged input reproduces identical scores because the response is cached by
  `(model, prompt_version, text)`, not because sampling was pinned.
* **All 38 meetings hand-labeled, not a subsample**, to compensate for FOMC's
  naturally small annual meeting count.

## Not yet done

The actual `make extract` run (needs `ANTHROPIC_API_KEY`) and therefore every real
reliability/IC/backtest number; a crypto-headline-based second text source (FOMC
statements were chosen as the more tractable, self-contained real-data source);
sourcing real-time market-implied probabilities to ground `surprise_magnitude`
precisely instead of the disclosed regime-transition heuristic; a committed copy
(or CI-fetched cache) of `pm-bayes-pricer`'s bar data, so `make analyze` could run
against a fresh clone or in CI without a local `make bars` step first; a
confidence-weighted reliability check that uses each hand label's own stated
confidence rather than treating all 38 labels as equally certain; the
project-audit skill's full five-checker pass against *real* numbers (deliberately
deferred — see `.claude/skills/project-audit/SKILL.md` — auditing PENDING results
would be meaningless; a pre-execution pipeline audit has already been run, see
`AUDIT.md`).
