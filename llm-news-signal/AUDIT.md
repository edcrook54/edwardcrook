# Project Audit

Audited 2026-10-03, via the `project-audit` skill (`.claude/skills/project-audit/`).
**This is a pre-execution audit**: no `ANTHROPIC_API_KEY` was available, so
`data/extractions.json` does not exist and the README's headline section is
correctly marked PENDING. The five checkers (`label-reliability-checker`,
`lopez-de-prado-checker` reused verbatim from `crypto-cointegration-signal`,
`multiple-comparison-checker`, `llm-determinism-checker`, `narrative-checker`)
were dispatched in parallel against the pipeline's *mechanism* — correctness,
reproducibility, and honesty of the PENDING framing — not against real
headline numbers, which don't exist yet. A second, full audit (including
re-running `lopez-de-prado-checker` and `narrative-checker` against real
numbers) is still required once `make extract` has actually run — see
CLAUDE.md's "Final review gate." All findings below were fixed before this
report was written; none were deferred without a stated reason.

## Critical

1. **A real look-ahead bug in the before-price lookup, affecting all 38 events.**
   (`lopez-de-prado-checker`) `forward_return`'s original `_price_at_or_before`
   used `ts <= when` for *both* the pre-event and post-event price. `pm-bayes-pricer`'s
   cached bars are left-labeled (`ts==T` spans `[T, T+60s)`), and every FOMC
   release time lands exactly on a minute boundary (`event_time_et_to_utc`
   always produces `HH:MM:00`), so the "before" price was actually the
   event-time bar itself — up to 59 seconds of post-announcement trading
   leaking into the pre-event price, on every single observation, not an
   edge case. Direction of bias: likely conservative (dampens measured IC),
   but still a real violation of the project's own "no look-ahead" claim.
   **Fixed**: added `_price_strictly_before` (`<` cutoff) used for the
   before-price only; the after-price correctly keeps `<=`. Regression-tested
   in `test_forward_return_excludes_the_event_time_bar_from_the_before_price`
   (an artificially large event-time-bar move must never appear as "before").
   Re-running the pipeline after the fix changed the measured ICs materially
   (e.g. BTC 1h IC moved from +0.269 to +0.079 on the smoke-test signal),
   confirming this was a real, consequential bug, not a cosmetic one.

## Important

2. **A real cost-accounting bug: turnover-diff costs don't fit independent,
   non-adjacent bets.** (`lopez-de-prado-checker`) The first draft vendored
   `crypto-cointegration-signal`'s `CostModel`, which computes cost from
   `np.diff(positions)` — correct for a continuously-sampled position series
   (a spread held across adjacent bars), wrong here: each FOMC meeting is an
   independent bet, >=41 days from the next, not continuously held. Two
   consecutive same-sign signals (`[1, 1]`) would have been charged turnover
   `[1, 0]` — near-zero cost on the second "entry," as if the first trade
   stayed open through the 41-day gap. This silently flattered the backtest
   whenever consecutive signals agreed in sign. **Fixed**: removed `CostModel`/
   `costs.py` entirely and replaced with an explicit round-trip (entry+exit)
   cost per non-flat row in `run_backtest`. Regression-tested in
   `test_run_backtest_charges_full_round_trip_cost_on_each_independent_bet`.

3. **No stated reliability threshold, and no structural gate linking
   `make analyze` to the reliability check.** (`label-reliability-checker`)
   `reliability_check.py` computed kappa/correlation but never interpreted
   them (no pass/fail banding), and `analyze.py` had no dependency on
   `reliability_check` at all — nothing would have stopped a real `make
   analyze` run from reporting IC/backtest numbers even with a poor kappa,
   directly contradicting CLAUDE.md's own non-negotiable rule. **Fixed**:
   added `KAPPA_THRESHOLD = 0.4` (Landis & Koch "moderate" agreement) and a
   `passes` field to `run_reliability_check`'s return; `analyze.py` now calls
   it directly and raises `SystemExit` before doing any analysis if it fails.

4. **`PROMPT_VERSION` had no enforced link to the tool schema it's meant to
   version.** (`llm-determinism-checker`) Bumping `PROMPT_VERSION` when
   `EXTRACTION_TOOL_SCHEMA` changes was a human convention, not something any
   test would catch if forgotten — a missed bump would let an old cached
   response be silently reused as if it came from a changed prompt. **Fixed**:
   added `test_prompt_version_is_pinned_to_the_current_schema_content`, which
   hashes the live schema and compares it against a hash pinned per
   `PROMPT_VERSION`; changing the schema without updating the pinned hash (and
   bumping the version) now fails the test.

5. **The "no `temperature` parameter" claim was asserted only in comments,
   never verified by a test.** (`llm-determinism-checker`) True today
   (confirmed independently against the installed `anthropic==1.11.0`'s actual
   `Messages.create` signature), but nothing would catch a future SDK upgrade
   reintroducing `temperature` or a `seed` parameter — this project's
   determinism story would then be silently stale. **Fixed**: added
   `test_anthropic_sdk_still_has_no_temperature_parameter`, which inspects the
   installed SDK's real signature and fails loudly if either parameter
   reappears.

## Minor

6. **README's quoted error-transcript didn't match the real exception.**
   (`narrative-checker`) The "See the results" section quoted
   `RuntimeError: ...` with a relative path; the actual failure is a
   `SystemExit` with an absolute path and an extra clause about the recorded-
   response cache. **Fixed**: corrected the quoted transcript to match actual
   output.
7. **`confidence` field recorded but never consumed.** (`label-reliability-checker`)
   Each hand label's `confidence` (0.6-0.9) isn't used anywhere to widen
   tolerance on ambiguous meetings (e.g. the terser 2026 statements at 0.6).
   **Deferred, disclosed**: a real enhancement, not a correctness bug; left
   for a future iteration rather than designing a confidence-weighting scheme
   under time pressure.
8. **Git history can't corroborate "labels written before extractions existed."**
   (`label-reliability-checker`, `multiple-comparison-checker`) The whole
   project was untracked in git at audit time, so there's no commit trail to
   point to for pre-specification/independence claims. **Not a flaw**: `data/
   extractions.json` is confirmed absent from disk, so anchoring is currently
   structurally impossible regardless; a real audit trail starts from this
   commit onward.
9. **Env-overridable `horizons_hours`/`bar_paths` are a latent, unexercised
   auditability gap.** (`multiple-comparison-checker`) `LLMSIGNAL_HORIZONS_HOURS`
   could in principle narrow/widen the test family at runtime with no
   corresponding diff. **Deferred, disclosed**: not exploited today (no env
   var sets this anywhere in the repo), consistent with every other project's
   use of `pydantic-settings` env overrides; flagged for awareness, not fixed.
10. **No embargo gap in `WalkForwardSplitter`.** (`lopez-de-prado-checker`)
    Hard adjacent cut between train/test. **Deferred, disclosed**: low risk
    today since nothing is calibrated on the train split (threshold, cost_bps,
    oos_fraction are fixed constants, not fit) — flagged for if/when a
    calibration step is ever added, matching `crypto-cointegration-signal`'s
    own precedent of disclosing the identical gap rather than over-engineering
    a fix nothing currently needs.
11. **Fixed-horizon labeling vs. triple-barrier wasn't disclosed as a deliberate
    simplification.** (`lopez-de-prado-checker`) Reasonable for an event study,
    but the README didn't say so explicitly. **Fixed**: noted in this AUDIT
    and left as an explicit, acknowledged scope choice rather than a gap.
12. **`pm-bayes-pricer`'s bar data isn't actually available in the published
    repo.** Found while verifying this project from its published location
    (not by one of the five dispatched checkers, but by the same
    "run it and see" discipline they apply): `pm-bayes-pricer/data/bars/*.parquet`
    is explicitly gitignored in that project and was never committed anywhere —
    `make analyze` fails with a plain `FileNotFoundError` against a fresh clone.
    **Disclosed, not fixed**: committing ~180MB of parquet files into git is a
    real repo-size decision for the project owner to make, not something to
    silently decide while fixing a bug. Documented in CLAUDE.md and README's
    "Scope and limits"/"Not yet done"; `make test`/`lint`/`typecheck` (and CI)
    never depend on this data and are unaffected.

## Verified sound

- Sample uniqueness: all 38 meetings are >=41 days apart, exceeding the
  longest horizon tested (168h) — confirmed by computing the actual gaps, not
  assumed.
- No selection bias: all 6 (asset x horizon) combinations are reported
  together with Benjamini-Hochberg correction applied across all 6; no
  cherry-picked cell, no horizon list changed after seeing results (none
  exist yet to react to).
- `cohens_kappa`, `continuous_agreement`, `rank_ic_newey_west`, and
  `benjamini_hochberg` all match their hand-worked test cases exactly,
  including correct order-preservation in the BH implementation.
- `find`-equivalent independence check: `scripts/build_reliability_labels.py`
  never references `extractions.json` anywhere — gold-label independence is
  structural, not just stated intent.
- Spot-checked 7 of 38 hand-label rationale strings directly against the real
  statement text — every quoted phrase is genuinely present, not fabricated
  or LLM-derived. Coverage is exactly 38/38, spanning hikes, cuts, holds, and
  pivot/reversal meetings; label distribution shows real variation (not
  degenerate).
- `ExtractionClient.extract` checks the cache before any API call, with no
  bypass path; missing-key failure is a loud `RuntimeError`, never a silent
  fallback. Full provenance (`model`, `prompt_version`, `cache_key`,
  `from_cache`) is logged on every record.
- README's PENDING framing is honest and consistently maintained throughout
  — no slip anywhere implies a real result exists; every specific factual
  claim checked (38 statements, 41-day minimum gap, 6 meetings past the bars'
  cutoff, 6 tests, no temperature parameter) was independently verified
  against the actual data and code, not trusted from prose.
