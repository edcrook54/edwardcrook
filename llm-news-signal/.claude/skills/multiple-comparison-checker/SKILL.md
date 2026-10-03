---
name: multiple-comparison-checker
description: Use when reviewing how many statistical tests were run and whether significance claims across them are corrected for multiple comparisons - triggers on "Benjamini-Hochberg", "FDR correction", "multiple testing", "how many tests", "corrected p-value", "cherry-picked horizon".
---

# Multiple Comparison Checker

## Overview

This project runs a rank-IC significance test across every combination of
asset (BTC, ETH) and horizon (1h, 24h, 168h) - 6 tests. This skill checks
whether that full count is disclosed and corrected for, and specifically
whether the write-up resists reporting only the best-looking cell as if it
were the single pre-specified test.

## When to Use

Before accepting any IC/significance claim from `make analyze` or the
README's headline section.

## Core Checklist

### 1. Is the full test count disclosed?

- Count the actual cross-product being tested: `len(settings.bar_paths) *
  len(settings.horizons_hours)` in `analyze.py` - confirm this matches what
  `benjamini_hochberg` is actually called with (`len(p_values)`), and that
  the README states this count explicitly rather than discussing results
  asset-by-asset or horizon-by-horizon in a way that obscures how many
  independent looks were taken.

### 2. Benjamini-Hochberg correctness

- Verify against `tests/test_stats.py`'s hand-worked example: thresholds
  are `(rank/m)*alpha` over p-values sorted ascending, and the significance
  cutoff is the *largest* rank whose p-value still falls below its own
  threshold - not the first, and not a fixed single threshold applied to
  every p-value independently (that would just be an uncorrected test
  repeated m times).
- Confirm `benjamini_hochberg`'s output order matches the input order
  (`tests/test_stats.py::test_benjamini_hochberg_preserves_input_order`) -
  an order bug here would silently mislabel which asset/horizon survived
  correction.

### 3. Is the headline framed around the corrected result?

- If none of the 6 tests survive BH correction, confirm the README's
  headline section says so plainly, rather than leading with the single
  most significant *uncorrected* p-value (e.g. "ETH at 1 hour shows p=0.047"
  presented as the finding, with the correction mentioned only afterward as
  a footnote). The corrected conclusion is the actual finding; the
  uncorrected per-cell numbers are supporting detail.
- Check whether the choice of horizons (1h, 24h, 168h) and the decision to
  test both BTC and ETH were made *before* seeing any results, not
  expanded or narrowed afterward based on which combination looked best -
  if the project's commit history shows horizons changed after a first
  `make analyze` run, that's a form of the garden-of-forking-paths problem
  even without literal p-hacking intent.

### 4. Interaction with the reliability check

- If `label-reliability-checker` finds the extraction unreliable, confirm
  that caveat propagates here: an IC test on a noisy, unreliable score adds
  another layer of multiplicity risk (noise in the input makes a spuriously
  significant correlation in a six-test family more, not less, concerning)
  rather than being an unrelated finding reported alongside this one without
  cross-reference.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Full count disclosed | README states "6 tests" explicitly | Results discussed piecemeal, true count obscured |
| BH formula | Matches hand-worked test exactly, correct ordering | Largest-surviving-rank logic inverted or off-by-one |
| Headline framing | Corrected conclusion leads | Best uncorrected p-value leads, correction is a footnote |
| Pre-specification | Horizons/assets fixed before first results seen | Horizon list changed after seeing which one "worked" |

## Red Flags

- A README that reports "p=0.047" prominently without immediately stating
  what it becomes after BH correction across all 6 tests.
- Any sign the set of horizons tested was adjusted after an initial run.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "ETH at 1 hour is significant before correction, that's still worth mentioning" | It's worth mentioning *as an uncorrected number explicitly labeled as such* - presented without that label, a reader has no way to judge it against the other five tests that were also run. |
| "We only really cared about the 24h horizon anyway" | If 1h and 168h were run and reported at all, they count as tests taken, regardless of which one the author expected to matter most going in. |

## Output Format

Report findings as Critical / Important / Minor with file:line references,
plus an explicit list of what was checked and verified as sound.
