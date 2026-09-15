---
name: probability-test-checker
description: Use when reviewing a project's statistical hypothesis tests, p-values, significance claims, or confidence intervals for methodological correctness - triggers on "p-value", "significance level", "cointegration test", "unit root", "multiple testing", "hypothesis test", "confidence interval", "t-stat", "Sharpe ratio significance".
---

# Probability Test Checker

## Overview

This skill checks whether the statistical tests a project runs are
*valid for the question being asked*, not just whether they were run
without error. A test can execute cleanly, produce a plausible-looking
p-value, and still be the wrong test, applied to the wrong number of
comparisons, on inputs that don't satisfy its own assumptions. This is a
general statistics review - for financial-ML-specific concerns (bet
sizing, sample uniqueness, backtest-selection bias) see
`lopez-de-prado-checker`, which overlaps with this skill on some findings
by design: independent convergence from two different angles on the same
root cause is a stronger signal than either alone, and should be called
out as such rather than deduplicated away.

## When to Use

Any time a project reports a statistical test result (p-value,
confidence interval, significance claim) as part of its evidence for a
trading signal, a relationship between series, or a backtest's
performance.

## Core Checklist

### 1. Are the test's own assumptions actually satisfied?

- For a cointegration test (Engle-Granger, Johansen): both input series
  must be integrated of the same order (typically I(1)) for the test to
  be meaningful. Check whether a unit-root test (e.g. ADF) was run on
  each *individual* series before testing them jointly for cointegration.
  If not, the cointegration p-value could reflect something other than a
  genuine cointegrating relationship - flag this as a missing
  prerequisite check, even if the cointegration test itself ran without
  error.
- For any parametric test, check whether the underlying series has
  properties (heavy duplication, extreme skew, non-stationarity beyond
  what the test handles) that were already documented elsewhere in the
  project as a data-quality caveat - if so, confirm that caveat is
  connected explicitly to *this* test's validity, not left as a generic
  disclaimer.

### 2. Multiple comparisons

- Count the total number of hypothesis tests actually run (pairs x
  windows x parameter sets, whatever the full cross-product is). At a
  nominal alpha of 0.05, N independent tests produce an expected
  `0.05 * N` false positives under the global null - compute this number
  for the project's actual N and compare it to the number of "significant"
  results actually reported. If the reported count isn't meaningfully
  above the chance-false-positive count, that's a **Critical** finding:
  the headline result may not be distinguishable from noise.
- Check whether any correction (Bonferroni, Benjamini-Hochberg/FDR) was
  applied, or whether the write-up at least states the uncorrected count
  alongside the raw significant-fraction metric so a reader can judge for
  themselves.

### 3. Are the tests actually independent?

- Multiple-testing corrections (Bonferroni especially) assume the tests
  are independent. If "many random windows" are sampled from a bounded
  history with a window length that is a non-trivial fraction of the
  total series length, check the math: with N draws from
  `(series_length - window_length)` possible start points and a window
  width `W`, overlapping windows are close to guaranteed once
  `N * W >> series_length`. Overlapping windows share data, so their
  p-values are correlated, not independent - this simultaneously (a)
  makes a naive Bonferroni correction too conservative in one sense and
  invalid in another, and (b) means the "stability" a high
  fraction-significant metric implies is partly mechanical (adjacent
  overlapping windows agreeing with each other) rather than N independent
  confirmations. Quantify the actual overlap (expected pairwise overlap
  fraction given N, W, and series length) and report it plainly.

### 4. Point estimates without uncertainty

- Any backtest performance number (Sharpe ratio, hit rate, total return)
  reported to 2+ decimal places without an accompanying measure of
  uncertainty (standard error, confidence interval, or at minimum the
  effective sample size it's based on) should be flagged as incomplete,
  not wrong. The standard asymptotic Sharpe SE,
  `sqrt((1 + 0.5*SR^2) / N)`, is a reasonable minimum bar - but note
  explicitly that it assumes IID returns, which serially correlated
  held-position returns violate (cross-reference
  `lopez-de-prado-checker`'s sample-uniqueness finding here rather than
  re-deriving it).

### 5. p-value interpretation and honesty

- Check the write-up doesn't claim "proof," "confirmation," or
  "significance" from a single low p-value where the project's own
  design (e.g. a distribution-over-many-windows approach) was explicitly
  built to avoid exactly that kind of single-draw overclaiming. Give this
  an explicit **pass** if the narrative already reports distributions
  rather than cherry-picked single numbers - say so, don't just hunt for
  violations.
- Check that "not significant" is never silently treated as "no
  relationship" - absence of significance at a chosen alpha is not
  evidence of absence, especially with the sample sizes actually
  available here.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Test assumptions | Unit-root/prerequisite checked before dependent test | Test run on unchecked inputs |
| Multiple comparisons | Corrected, or chance-false-positive count disclosed | Raw significant-count reported with no context |
| Test independence | Overlap quantified if windows are sampled | "N random windows" treated as N independent draws |
| Uncertainty | SE/CI or effective-N alongside point estimate | Bare point estimate to 2 decimals |
| p-value honesty | Distribution reported, single draws not over-claimed | "p < 0.05" used as proof |

## Red Flags

- `alpha = 0.05` used across dozens+ of tests with no mention of the
  expected false-positive count under the global null.
- A cointegration/stationarity test run without a prior unit-root check
  on the inputs.
- "Random windows" whose combined width, given the sampling count,
  mathematically must overlap - treated in the write-up as independent
  evidence.
- Any Sharpe/return figure with no N, no SE, and no mention of how many
  independent bets it reflects.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "We report the whole distribution, so multiple testing doesn't matter" | Reporting the distribution is necessary but not sufficient - the *selection decision* made from that distribution (picking the best pair) is still subject to selection bias regardless of how honestly the distribution itself is presented. |
| "The windows are randomly sampled, so they're independent" | Random sampling controls *which* windows are drawn, not whether the drawn windows overlap in content; independence requires disjoint data, not just a random start index. |
| "statsmodels' coint() handles all of that internally" | `coint()` runs the Engle-Granger regression and ADF-on-residuals correctly, but it does not verify that the two input series are I(1) to begin with - that check is the caller's responsibility. |

## Output Format

Report findings as Critical / Important / Minor with `file:line` or
notebook cell references, the specific number that would change if fixed
(e.g. "expected ~15 false positives at alpha=0.05 across 300 tests"), and
a concrete next step. List explicit passes alongside failures.
