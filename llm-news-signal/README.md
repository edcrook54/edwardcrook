# llm-news-signal

Does an LLM-extracted hawkish/dovish score from real FOMC statements predict
BTC/ETH forward returns? Same rigor as `crypto-cointegration-signal`
(walk-forward, cost-adjusted, multiple-comparison-aware). LLM is a feature
extractor here, not an agent — the deliverable is the stats.

## ⚠ headline result: PENDING

No `ANTHROPIC_API_KEY` at build time, so no real extraction happened.
**No API key committed here either, on purpose — don't want a stranger
burning my Anthropic credits lol.** Rather than fake a number, the whole
pipeline is built and tested against a placeholder signal instead, and says
so plainly. Run `make extract` yourself with your own key to get the real one.

```
$ make test
...33 passed

$ make reliability   # exits, pointing at make extract - this is correct
```

## scope

- **38 real FOMC statements**, Jan 2022–Sep 2026, verbatim from
  federalreserve.gov. Smaller than a 50-100-example study because FOMC only
  meets ~8x/year — compensated by hand-labeling all 38, not a subsample.
- **Real cached BTC/ETH bars** from `pm-bayes-pricer`. 6 of 38 meetings fall
  past the bars' cutoff, correctly excluded, not faked.
- `pm-bayes-pricer`'s bar files aren't committed anywhere (gitignored on
  purpose, ~180MB). `make test/lint/typecheck` don't need them. Only
  `make analyze` does — run `pm-bayes-pricer`'s `make bars` first.
- `surprise_magnitude` uses a disclosed heuristic (regime-transition
  position), not real market-implied odds — I don't have that data locally.

## what's actually verified

- no look-ahead: "before" price is strictly before the event, tested
- no overlapping event windows (min gap 41 days > longest horizon 168h)
- gold labels written from raw statements, before any extraction existed
- installed `anthropic` SDK has no `temperature` param (removed upstream) —
  determinism = response caching instead, pinned by a test
- `make analyze` physically can't run on unreliable extractions — calls the
  reliability check itself, refuses below kappa 0.4 (Landis & Koch)

## bugs the audit caught

- **look-ahead bug**: "before" price used `<=` instead of `<`, leaking up to
  59s of post-announcement trading into every single one of the 38 events —
  fixed
- **cost-accounting bug**: vendored a turnover-diff cost model that assumed
  continuously-held positions; these are independent bets 41+ days apart, so
  consecutive same-sign bets got charged almost nothing on the second one —
  fixed, model removed, explicit round-trip cost instead
- **reliability check computed a number but didn't gate anything** — fixed,
  `analyze.py` now calls it and refuses to proceed if it fails

full writeup in `AUDIT.md`.

## how it works

```
fomc_statements.json -> ExtractionClient (needs API key, PENDING)
  -> extractions.json -> reliability_check (kappa gate)
  -> analyze (join real bars -> rank-IC + Newey-West + Benjamini-Hochberg
     -> cost-adjusted backtest)
```

## run it

```bash
cp .env.example .env   # set your own ANTHROPIC_API_KEY
make install && make test && make lint && make typecheck
make extract && make reliability && make analyze   # needs a real key
```

## why

- LLM as feature extractor, not agent (see `trading-desk-agent` for agents)
- `WalkForwardSplitter` vendored not imported from `crypto-cointegration-signal`
  (that project isn't a package); `CostModel` was too, but didn't fit here —
  removed
- all 38 meetings hand-labeled, not a subsample, since there's only ~8/year

## not done

the real `make extract` run and every number downstream of it; a second
text source; real market-implied probabilities for surprise scoring;
committing/caching `pm-bayes-pricer`'s bars so CI could run `make analyze`;
confidence-weighted reliability (each label has a confidence score, unused
so far); full audit against real numbers (pre-execution audit already
done, see `AUDIT.md`).
