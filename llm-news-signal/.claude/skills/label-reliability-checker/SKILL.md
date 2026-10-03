---
name: label-reliability-checker
description: Use when reviewing whether an LLM used as a data labeler has been validated against independent human labels before its output is trusted in a downstream statistical test - triggers on "Cohen's kappa", "label reliability", "LLM as labeler", "inter-rater agreement", "gold labels", "reliability validation".
---

# Label Reliability Checker

## Overview

This project uses an LLM to extract a continuous sentiment score and a
categorical label from FOMC statement text, then feeds that into a
statistical test. The entire downstream analysis is only as trustworthy as
the extraction, so this skill checks whether the extraction was validated
as a labeling source would be validated from any other source - never
assumed reliable because it came from a capable model.

## When to Use

Before trusting any `make analyze` output, and specifically before
accepting `make reliability`'s kappa/correlation numbers as sufficient
validation.

## Core Checklist

### 1. Independence of the human labels

- Confirm every entry in `data/reliability_labels.json` was written by
  reading `data/fomc_statements.json` directly (check
  `scripts/build_reliability_labels.py`'s rationale strings reference the
  actual statement text/action/rate, not an LLM's output).
- Confirm the human labels were written (or at minimum, finalized) *before*
  any real `data/extractions.json` existed - if the labels were edited after
  seeing the LLM's scores, that's anchoring contamination even if the
  editor didn't intend it. Check git history / file timestamps if available.
- Confirm `data/extractions.json` is never imported by
  `scripts/build_reliability_labels.py` (grep for it) - the independence
  guarantee must be structural, not just by stated intent.

### 2. Coverage and representativeness

- Confirm the reliability sample covers the full range of what's being
  measured: both hiking and cutting regimes, holds adjacent to pivots
  (highest-information meetings) and holds deep in an established trend
  (lowest-information), not just the easy, obviously-hawkish or
  obviously-dovish statements. Given there are only 38 meetings total, the
  project's choice to hand-label all of them rather than a subsample should
  be treated as a strength, but check it's actually all 38, not a silently
  smaller set presented as complete coverage.
- Check whether any meeting's `confidence` in the human labels is itself
  disclosed as low, and whether the write-up accounts for that (a labeler's
  own uncertainty on an ambiguous statement should widen tolerance for
  disagreement with the LLM there, not count as a clean miss).

### 3. Kappa and correlation correctness

- Verify `cohens_kappa`'s formula against its own hand-worked test
  (`tests/test_reliability.py`) - `p_expected` must come from each rater's
  own marginal frequencies, not a uniform-chance assumption across
  categories.
- Check that `continuous_agreement`'s Pearson correlation, MAE, and bias are
  all reported together, not just correlation - a high correlation with a
  large constant bias (the LLM is consistently more hawkish than the human
  by some offset) is a different, more fixable problem than scattered
  disagreement, and the write-up should distinguish them.

### 4. Is the reliability bar actually met before trusting `make analyze`?

- There's no universally "correct" kappa threshold, but check the project
  states *some* threshold and its rationale (e.g. kappa > 0.4 = moderate
  agreement, a common rule of thumb) rather than reporting a kappa number
  with no interpretation attached.
- If kappa or correlation is low, check the README doesn't proceed to
  report the downstream IC/backtest numbers as if they were trustworthy
  without flagging that the labels feeding them are unreliable - a low
  kappa should be a loud caveat on every number that follows it, not a
  number buried in a separate section.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Label independence | Human labels traceable to source text, written before any LLM output existed | Labels edited after seeing LLM scores |
| Coverage | All 38 meetings, spanning hikes/cuts/holds/pivots | A subsample that skews toward easy, unambiguous cases |
| Kappa formula | Matches hand-worked test exactly | Chance-agreement computed from uniform priors, not marginals |
| Threshold stated | A reliability bar and its rationale are explicit | Kappa reported with no interpretation |
| Downstream caveat | Low reliability flagged loudly on every number after it | Low kappa buried while headline numbers are reported normally |

## Red Flags

- `reliability_labels.json` containing a rationale string that quotes or
  paraphrases an LLM's own extraction rather than the source statement.
- A reliability check run and reported, but the headline analysis
  proceeding regardless of what it found.
- All 38 labels landing suspiciously close to a `sentiment` majority class
  with no real variation - a sign the labeler wasn't actually discriminating.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "I wrote the human labels myself, so of course they're independent" | Self-authored labels are only independent if nothing from the system being validated leaked into the labeling process - the check is about process, not good intentions. |
| "Kappa is a nice-to-have, the IC test is what matters" | An IC test computed on an unreliable score is not evidence about FOMC-statement sentiment at all - it's evidence about whatever noise process generated the scores. |

## Output Format

Report findings as Critical / Important / Minor, each citing the specific
file/record involved, plus an explicit list of what was checked and
verified as sound.
