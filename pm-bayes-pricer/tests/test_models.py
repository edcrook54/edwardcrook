import numpy as np
import pytest

from pmq.models.dirichlet import DirichletBelief, counts_from_outcome
from pmq.models.pooling import fit_weight_on_model, pool_binary, pool_categorical


def test_update_adds_counts_and_pulls_the_mean() -> None:
    prior = DirichletBelief(("cut", "hold", "hike"), np.array([2.0, 6.0, 2.0]))
    post = prior.update(counts_from_outcome(0, 3))
    assert post.alpha.tolist() == [3.0, 6.0, 2.0]
    assert post.mean()[0] > prior.mean()[0]
    assert post.mean().sum() == pytest.approx(1.0)


def test_more_evidence_narrows_the_credible_interval() -> None:
    prior = DirichletBelief.from_probabilities(("a", "b"), [0.5, 0.5], strength=4)
    wide = prior.credible_interval()[0]
    narrow = prior.update([50, 50]).credible_interval()[0]
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_sequential_updating_equals_batch_updating() -> None:
    prior = DirichletBelief(("a", "b", "c"), np.ones(3))
    step = prior
    for i in (0, 0, 1, 2, 0):
        step = step.update(counts_from_outcome(i, 3))
    batch = prior.update([3, 1, 1])
    assert step.alpha.tolist() == batch.alpha.tolist()


def test_evidence_prefers_the_prior_that_predicted_the_data() -> None:
    labels = ("cut", "hold", "hike")
    hold_heavy = DirichletBelief.from_probabilities(labels, [0.1, 0.8, 0.1], strength=10)
    flat = DirichletBelief.from_probabilities(labels, [1 / 3] * 3, strength=10)
    data = [1, 8, 1]
    assert hold_heavy.log_evidence(data) > flat.log_evidence(data)


def test_samples_are_valid_probability_vectors() -> None:
    belief = DirichletBelief(("a", "b", "c"), np.array([3.0, 5.0, 2.0]))
    draws = belief.sample(1000, np.random.default_rng(0))
    assert draws.sum(axis=1) == pytest.approx(np.ones(1000))
    assert draws.mean(axis=0) == pytest.approx(belief.mean(), abs=0.03)


def test_pooling_endpoints_and_overconfidence_property() -> None:
    assert pool_binary(0.7, 0.4, 0.0) == pytest.approx(0.4)
    assert pool_binary(0.7, 0.4, 1.0) == pytest.approx(0.7)
    both_90 = pool_categorical([[0.9, 0.1], [0.9, 0.1]], [0.5, 0.5])
    assert both_90[0] == pytest.approx(0.9)  # weights sum to 1, so agreement is preserved


def test_categorical_pool_is_a_distribution() -> None:
    pooled = pool_categorical([[0.6, 0.3, 0.1], [0.2, 0.5, 0.3]], [0.4, 0.6])
    assert pooled.sum() == pytest.approx(1.0) and np.all(pooled > 0)


def test_fitted_weight_is_zero_when_model_is_noise_and_high_when_model_is_informative() -> None:
    rng = np.random.default_rng(3)
    truth = rng.uniform(0.1, 0.9, 4000)
    y = (rng.random(4000) < truth).astype(float)
    market = np.clip(truth + rng.normal(0, 0.02, 4000), 0.02, 0.98)  # nearly the truth
    noise_model = rng.uniform(0.05, 0.95, 4000)
    w_noise, _ = fit_weight_on_model(noise_model, market, y)
    assert w_noise < 0.1
    noisy_market = np.clip(truth + rng.normal(0, 0.25, 4000), 0.02, 0.98)
    good_model = np.clip(truth + rng.normal(0, 0.02, 4000), 0.02, 0.98)
    w_good, _ = fit_weight_on_model(good_model, noisy_market, y)
    assert w_good > 0.7
