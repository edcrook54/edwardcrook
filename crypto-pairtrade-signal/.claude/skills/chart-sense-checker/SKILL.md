---
name: chart-sense-checker
description: Use when reviewing data visualizations, charts, or plots for visual honesty and clarity issues - triggers on "chart", "plot", "figure", "visualization", "axis", "colorbar", "colormap", "legend", "misleading", "chart junk".
---

# Chart Sense Checker

## Overview

A chart can be statistically accurate and still mislead through its
*presentation*: an inverted colour scale next to a normal one, a unit
left off an axis, a chart type poorly suited to the sample size behind
it. This skill reviews every generated figure for exactly that class of
issue - it assumes the underlying numbers are correct (that's
`probability-test-checker`'s and `narrative-checker`'s job) and asks
whether the chart *shows* those numbers honestly and legibly to someone
reading quickly.

## When to Use

Any time a project has produced saved figures (PNG/SVG) or inline
notebook plots as evidence for a claim, before those figures go into a
README, report, or presentation.

## Core Checklist

Open every figure the project generated (not just a sample) and check
each one against this list. Cite the filename for every finding.

### 1. Axis and scale honesty

- Log vs. linear: confirm log scale is used where the underlying values
  span multiple orders of magnitude (e.g. asset prices differing by
  100x+), and linear is used where a log scale would exaggerate
  small-magnitude noise. Give an explicit pass where this is already
  handled correctly.
- Truncated/non-zero baselines: a bar chart or area chart implying
  magnitude via height should start at zero unless there's a labeled,
  deliberate reason not to (e.g. a zoomed diagnostic view, clearly
  titled as such). Line charts of a value that can legitimately go
  negative (returns, drawdown) don't need a zero baseline, but should
  still draw a zero reference line so the sign is unambiguous at a
  glance.
- Units: every axis with a real-world quantity should be able to answer
  "is this a percent, a fraction, a multiple of capital, a raw price in
  which currency" without the reader needing to cross-reference the
  narrative text. A cumulative-return axis that goes above 1.0 with no
  unit label is a common, easy-to-miss offender - flag it even though
  the underlying number is correct, because the chart alone doesn't
  communicate it.

### 2. Colour encoding

- Sequential data (a value that increases: time, magnitude, probability)
  should use a sequential/perceptually-uniform colormap (viridis, mako,
  rocket, crest...), not a qualitative one.
- Categorical data (asset name, regime label) should use a qualitative
  palette with enough hue separation to be distinguishable, and should
  be checked for colorblind-safety where the choice was hand-picked
  rather than a validated palette default.
- **Multi-panel colour direction consistency**: if two or more panels
  are shown side by side (e.g. two heatmaps of related metrics), check
  whether "more of the thing" maps to the same visual direction (e.g.
  both dark = high, or both light = high) in every panel. A pair of
  heatmaps where one uses a reversed colormap relative to the other -
  even if each is individually labeled correctly - is a classic
  fast-reading trap: a reader comparing panels by eye will misread which
  shade means "stronger" in at least one of them. This is worth flagging
  even when both panels are technically correct in isolation.
- Diverging data (correlation, anything centered on a meaningful zero)
  should use a diverging colormap centered at that zero, with the centre
  point stated (`vmin`/`vmax` symmetric around 0), not an off-centre
  sequential map.

### 3. Chart type fit for the sample size

- Boxenplots (letter-value plots) are built for distributions with
  thousands+ of points; on a distribution with n in the tens, most of
  the extra quantile detail a boxenplot adds over a plain boxplot or
  strip/violin plot is noise, not signal. Check n behind every
  distributional chart and flag boxenplots on small-n data as a
  stylistic mismatch (not wrong, just not the best-fit tool).
- Scatter plots with very large point counts should use alpha
  transparency or hexbin/2D-density to avoid overplotting hiding the
  true density; check this was done where point counts are large enough
  to matter.

### 4. Claim-to-chart correspondence

- For every figure referenced by a caption, title, or surrounding prose
  claim, check the chart actually shows what the claim says. A title
  that says "X vs Y" should have X and Y as the two encoded variables
  the reader would guess from the axis labels alone, not require
  reading the code to confirm.
- Check legends are present and legible wherever more than one series or
  category is plotted, and that legend entries use the same terminology
  as the axis labels and surrounding text (e.g. don't call something
  "regime" in the legend and "position" in the prose without connecting
  the two).

### 5. Chart junk and density

- Flag unnecessary gridlines, redundant tick labels, or decorative
  elements that don't carry information, but don't over-index on this -
  a clean, information-dense chart with sensible gridlines is not chart
  junk. The bar is "does removing this element lose information a reader
  needs," not "is this the minimal possible chart."

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Scale | Log used where magnitudes span orders; linear elsewhere | Linear scale hiding small-asset variation |
| Baseline | Zero baseline or explicit zero reference line | Implied-zero chart with no reference line |
| Units | Axis alone answers "percent/fraction/multiple/currency" | Unitless axis relying on external text |
| Colour direction | Same "more = darker/lighter" convention across paired panels | Inverted colormap in one of two side-by-side panels |
| Colour type | Sequential for ordered, qualitative for categorical, diverging for signed | Qualitative palette on ordered data or vice versa |
| Chart-fit | Chart type suits the n behind it | Boxenplot on n~50 |
| Claim match | Title/caption matches encoded variables exactly | Caption implies more than the axes show |

## Red Flags

- Two heatmaps or colour-encoded panels shown side by side with
  different colormap *directions* for what a reader would assume is a
  comparable "more/less" quantity.
- A cumulative-return or index-value axis with no unit and no percent
  sign, where the surrounding text quotes a percentage.
- A boxenplot, violin, or KDE on a sample size small enough that the
  chart implies more distributional detail than the data supports.
- Any chart whose title claims a relationship (correlation, causation,
  "predicts") stronger than what the encoded variables can show.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "The colorbar is labeled, so the direction is clear" | A labeled colorbar tells a careful reader the direction on *that panel*; it doesn't stop a reader comparing two panels at a glance from assuming a shared convention that isn't actually there. |
| "Anyone reading closely will get the units from the text" | The chart should be self-contained - a reader who screenshots or crops the figure loses the surrounding text. |
| "It's just a stylistic choice, not wrong" | Stylistic mismatches are still worth flagging as Minor - the bar for this skill is "could this be read wrong at a glance," not just "is it technically incorrect." |

## Output Format

Report findings as Critical / Important / Minor per figure (filename),
with a one-line description of the specific visual risk and a concrete
fix (e.g. "swap `cmap='rocket'` to `cmap='rocket_r'` on the mean-p-value
panel so both panels agree that darker = more cointegrated"). Explicitly
list figures that passed cleanly, not just the ones with findings.
