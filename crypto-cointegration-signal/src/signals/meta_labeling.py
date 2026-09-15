"""
Triple-barrier labeling and meta-labeling for conviction-scaled bet sizing.

Standard AFML pattern (Lopez de Prado, ch. 3), implemented from scratch here
rather than pulled in as a dependency - consistent with the rest of this
project - but directly inspired by Hudson & Thames' MlFinLab, the reference
implementation of these techniques, found via
https://github.com/paperswithbacktest/awesome-systematic-trading while
scoping this extension.

The primary model (ZScoreSignalGenerator) decides direction only - when to
enter, and which side. It previously also decided the exit unconditionally
(z-score reversion) with no stop-loss or maximum holding period, and every
entry was sized identically regardless of how strong the signal looked. Two
things fix that:

1. Triple-barrier labeling: for every primary-model entry, walk forward
   until one of three barriers is hit - profit-take (z reverts, same
   condition as the primary exit), stop-loss (z moves further adverse past
   a wider threshold), or a maximum holding period (timeout). This replaces
   the "hold until reversion, however long that takes" exit with a bounded
   one, and produces a binary label per entry (did the bet pay off before
   something worse happened or time ran out) for the meta-model to learn
   from.
2. Meta-labeling: a secondary classifier (here, gradient-boosted trees)
   trained on those labels predicts the probability the primary model's
   next bet will pay off, sized via bet_size = max(2p - 1, 0) - so a
   just-past-threshold entry and a high-conviction one are no longer
   treated identically, without changing the primary model's own direction
   calls at all.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from xgboost import XGBClassifier


@dataclass
class BarrierEvent:
    entry_idx: int
    exit_idx: int
    direction: float
    label: int
    bars_held: int
    outcome: str


class TripleBarrierLabeler:
    """Labels each primary-model entry by which of three barriers it hits
    first: profit-take (z reverts inside exit_z), stop-loss (|z| exceeds
    stop_z), or a max-holding-period timeout. `stop_z` must be wider than
    the primary model's `entry_z` - it is a *worse* adverse move, not the
    entry threshold itself.
    """

    def __init__(self, exit_z: float, stop_z: float, max_holding: int):
        if stop_z <= exit_z:
            raise ValueError("stop_z must be wider than exit_z to act as a stop-loss.")
        self.exit_z = exit_z
        self.stop_z = stop_z
        self.max_holding = max_holding

    def find_entries(self, positions: np.ndarray) -> list[tuple[int, float]]:
        """Returns (entry_idx, direction) for every 0 -> nonzero transition."""
        positions = np.asarray(positions, dtype=float)
        transitions = np.flatnonzero((positions[1:] != 0) & (positions[:-1] == 0)) + 1
        return [(int(idx), float(np.sign(positions[idx]))) for idx in transitions]

    def label_events(self, zscore: np.ndarray, entries: list[tuple[int, float]]) -> list[BarrierEvent]:
        zscore = np.asarray(zscore, dtype=float)
        n = len(zscore)
        events = []
        for entry_idx, direction in entries:
            horizon = min(entry_idx + self.max_holding, n - 1)
            outcome, exit_idx = "timeout", horizon
            for t in range(entry_idx + 1, horizon + 1):
                z = zscore[t]
                if np.isnan(z):
                    continue
                # Profit-take: the spread has reverted back inside the exit band.
                if abs(z) <= self.exit_z:
                    outcome, exit_idx = "profit_take", t
                    break
                # Stop-loss: the spread moved further adverse, past the wider stop.
                if direction > 0 and z <= -self.stop_z:
                    outcome, exit_idx = "stop_loss", t
                    break
                if direction < 0 and z >= self.stop_z:
                    outcome, exit_idx = "stop_loss", t
                    break
            label = 1 if outcome == "profit_take" else 0
            events.append(
                BarrierEvent(
                    entry_idx=entry_idx,
                    exit_idx=exit_idx,
                    direction=direction,
                    label=label,
                    bars_held=exit_idx - entry_idx,
                    outcome=outcome,
                )
            )
        return events

    def positions_from_events(self, n_obs: int, events: list[BarrierEvent]) -> np.ndarray:
        """Rebuilds a position array where each entry is held only until its
        own triple-barrier exit, rather than the primary model's unbounded
        reversion-only exit - this is what actually closes the "no
        stop-loss / no max holding period" gap, independent of sizing.
        """
        positions = np.zeros(n_obs)
        for event in events:
            positions[event.entry_idx : event.exit_idx + 1] = event.direction
        return positions


class EntryFeatureBuilder:
    """Builds meta-model features for each entry event, using only data
    available strictly at-or-before the entry bar (causal by construction,
    since every feature here is a trailing statistic computed up to the
    entry index).
    """

    def __init__(self, vol_window: int = 20):
        self.vol_window = vol_window

    def build(
        self,
        entries: list[tuple[int, float]],
        zscore: np.ndarray,
        spread: np.ndarray,
        hedge_ratio: np.ndarray,
    ) -> pd.DataFrame:
        rows = []
        last_entry_idx = None
        for entry_idx, direction in entries:
            lo = max(entry_idx - self.vol_window, 0)
            rows.append(
                {
                    "entry_idx": entry_idx,
                    "abs_z_entry": abs(zscore[entry_idx]),
                    "spread_vol_trailing": float(np.std(spread[lo:entry_idx])) if entry_idx > lo else 0.0,
                    "hedge_ratio_vol_trailing": float(np.std(hedge_ratio[lo:entry_idx])) if entry_idx > lo else 0.0,
                    "bars_since_last_entry": entry_idx - last_entry_idx if last_entry_idx is not None else self.vol_window,
                }
            )
            last_entry_idx = entry_idx
        return pd.DataFrame(rows).set_index("entry_idx")


class MetaLabelClassifier:
    """Gradient-boosted classifier predicting the probability a primary-model
    entry will hit its profit-take barrier before its stop-loss/timeout.
    Deliberately shallow and regularised given the small number of discrete
    entry events (hundreds, not thousands) typical of a threshold-crossing
    signal - a deep model here would overfit long before it generalised.
    """

    def __init__(self, seed: int | None = None):
        self.model = XGBClassifier(
            n_estimators=50,
            max_depth=2,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            eval_metric="logloss",
            random_state=seed,
        )

    def fit(self, features: pd.DataFrame, labels: np.ndarray) -> "MetaLabelClassifier":
        self.model.fit(features, labels)
        return self

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(features)[:, 1]

    def feature_importances(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series(self.model.feature_importances_, index=features.columns).sort_values(ascending=False)


class ConvictionSizer:
    """Converts a meta-model's predicted probability into a bet size via the
    standard AFML formula: size = 2p - 1, floored at 0 (a predicted
    probability at or below 0.5 - no better than a coin flip on the primary
    model's own call - sizes to flat rather than a negative/flipped bet).
    """

    def __init__(self, min_probability: float = 0.5):
        self.min_probability = min_probability

    def size(self, direction: np.ndarray, probability: np.ndarray) -> np.ndarray:
        direction = np.asarray(direction, dtype=float)
        probability = np.asarray(probability, dtype=float)
        raw_size = np.clip(2 * probability - 1, 0.0, 1.0)
        raw_size = np.where(probability <= self.min_probability, 0.0, raw_size)
        return direction * raw_size

    def positions_from_events(
        self, n_obs: int, events: list[BarrierEvent], probabilities: np.ndarray
    ) -> np.ndarray:
        positions = np.zeros(n_obs)
        sizes = self.size(np.array([e.direction for e in events]), probabilities)
        for event, size in zip(events, sizes):
            positions[event.entry_idx : event.exit_idx + 1] = size
        return positions
