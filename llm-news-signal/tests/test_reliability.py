import pytest

from llmsignal.reliability.kappa import cohens_kappa, continuous_agreement


def test_cohens_kappa_matches_hand_worked_example() -> None:
    # p_observed = 4/5 = 0.8 (positions 0,2,3,4 agree; position 1 disagrees)
    # proportions: a: A=0.6, B=0.4; b: A=0.4, B=0.6
    # p_expected = 0.6*0.4 + 0.4*0.6 = 0.48
    # kappa = (0.8 - 0.48) / (1 - 0.48) = 0.32 / 0.52
    rater_a = ["A", "A", "B", "B", "A"]
    rater_b = ["A", "B", "B", "B", "A"]

    kappa = cohens_kappa(rater_a, rater_b)

    assert kappa == pytest.approx(0.32 / 0.52)


def test_cohens_kappa_is_one_for_perfect_agreement() -> None:
    labels = ["hawkish", "dovish", "neutral", "hawkish"]

    assert cohens_kappa(labels, labels) == pytest.approx(1.0)


def test_cohens_kappa_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same number"):
        cohens_kappa(["A", "B"], ["A"])


def test_continuous_agreement_matches_hand_worked_example() -> None:
    llm = [1.0, 2.0, 3.0]
    human = [1.0, 2.0, 3.0]

    result = continuous_agreement(llm, human)

    assert result["pearson_r"] == pytest.approx(1.0)
    assert result["mae"] == pytest.approx(0.0)
    assert result["bias"] == pytest.approx(0.0)


def test_continuous_agreement_bias_is_the_mean_signed_difference() -> None:
    # llm consistently 0.2 above human on every example -> MAE and bias both 0.2
    llm = [0.7, 0.9, 1.1]
    human = [0.5, 0.7, 0.9]

    result = continuous_agreement(llm, human)

    assert result["mae"] == pytest.approx(0.2)
    assert result["bias"] == pytest.approx(0.2)
