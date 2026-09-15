import numpy as np
import pandas as pd
import pytest

from src.signals.meta_labeling import (
    ConvictionSizer,
    EntryFeatureBuilder,
    MetaLabelClassifier,
    TripleBarrierLabeler,
)


def test_find_entries_detects_zero_to_nonzero_transitions():
    positions = np.array([0, 0, 1, 1, 0, -1, -1, 0])
    labeler = TripleBarrierLabeler(exit_z=0.5, stop_z=3.0, max_holding=10)
    entries = labeler.find_entries(positions)
    assert entries == [(2, 1.0), (5, -1.0)]


def test_stop_z_must_be_wider_than_exit_z():
    with pytest.raises(ValueError):
        TripleBarrierLabeler(exit_z=2.0, stop_z=1.0, max_holding=10)


def test_label_events_profit_take():
    # Long spread entry (direction +1) at a very negative z, reverts inside exit_z next bar.
    zscore = np.array([np.nan, -2.5, -0.3, 0.0, 0.0])
    labeler = TripleBarrierLabeler(exit_z=0.5, stop_z=4.0, max_holding=10)
    events = labeler.label_events(zscore, entries=[(1, 1.0)])
    assert events[0].label == 1
    assert events[0].outcome == "profit_take"
    assert events[0].exit_idx == 2


def test_label_events_stop_loss():
    zscore = np.array([np.nan, -2.5, -3.0, -4.5, -5.0])
    labeler = TripleBarrierLabeler(exit_z=0.5, stop_z=4.0, max_holding=10)
    events = labeler.label_events(zscore, entries=[(1, 1.0)])
    assert events[0].label == 0
    assert events[0].outcome == "stop_loss"


def test_label_events_timeout():
    zscore = np.full(10, -2.5)
    labeler = TripleBarrierLabeler(exit_z=0.5, stop_z=4.0, max_holding=3)
    events = labeler.label_events(zscore, entries=[(0, 1.0)])
    assert events[0].label == 0
    assert events[0].outcome == "timeout"
    assert events[0].exit_idx == 3


def test_positions_from_events_holds_only_within_barrier():
    events = TripleBarrierLabeler(exit_z=0.5, stop_z=4.0, max_holding=10).label_events(
        np.array([np.nan, -2.5, -0.3, 0.0, 0.0]), entries=[(1, 1.0)]
    )
    positions = TripleBarrierLabeler(exit_z=0.5, stop_z=4.0, max_holding=10).positions_from_events(5, events)
    assert list(positions) == [0.0, 1.0, 1.0, 0.0, 0.0]


def test_entry_feature_builder_is_causal_and_complete():
    rng = np.random.default_rng(0)
    n = 100
    zscore = rng.normal(size=n)
    spread = np.cumsum(rng.normal(size=n))
    hedge_ratio = np.cumsum(rng.normal(scale=0.1, size=n)) + 1
    entries = [(10, 1.0), (40, -1.0), (70, 1.0)]

    features = EntryFeatureBuilder(vol_window=20).build(entries, zscore, spread, hedge_ratio)
    assert list(features.index) == [10, 40, 70]
    assert set(features.columns) == {
        "abs_z_entry", "spread_vol_trailing", "hedge_ratio_vol_trailing", "bars_since_last_entry",
    }
    assert not features.isna().any().any()


def test_conviction_sizer_floors_low_probability_to_flat():
    sizer = ConvictionSizer(min_probability=0.5)
    direction = np.array([1.0, 1.0, -1.0])
    probability = np.array([0.5, 0.9, 0.9])
    sizes = sizer.size(direction, probability)
    assert sizes[0] == 0.0
    assert sizes[1] == pytest.approx(0.8)
    assert sizes[2] == pytest.approx(-0.8)


def test_meta_label_classifier_learns_separable_signal():
    rng = np.random.default_rng(1)
    n = 200
    # Feature 0 is fully predictive of the label; the model should learn this easily.
    x0 = rng.normal(size=n)
    labels = (x0 > 0).astype(int)
    features = pd.DataFrame({
        "abs_z_entry": x0,
        "spread_vol_trailing": rng.normal(size=n),
        "hedge_ratio_vol_trailing": rng.normal(size=n),
        "bars_since_last_entry": rng.integers(1, 50, size=n),
    })

    clf = MetaLabelClassifier(seed=0).fit(features, labels)
    probs = clf.predict_proba(features)
    predicted = (probs > 0.5).astype(int)
    accuracy = (predicted == labels).mean()
    assert accuracy > 0.85

    importances = clf.feature_importances(features)
    assert importances.idxmax() == "abs_z_entry"
