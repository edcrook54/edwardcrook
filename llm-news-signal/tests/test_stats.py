import numpy as np
import pytest

from llmsignal.stats.ic import benjamini_hochberg, rank_ic_newey_west


def test_rank_ic_is_one_for_a_perfectly_monotonic_relationship() -> None:
    scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])

    result = rank_ic_newey_west(scores, returns)

    assert result["ic"] == pytest.approx(1.0)
    assert result["n"] == 5.0


def test_rank_ic_is_minus_one_for_a_perfectly_inverse_relationship() -> None:
    scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    returns = np.array([0.05, 0.04, 0.03, 0.02, 0.01])

    result = rank_ic_newey_west(scores, returns)

    assert result["ic"] == pytest.approx(-1.0)


def test_rank_ic_raises_below_three_observations() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        rank_ic_newey_west(np.array([1.0, 2.0]), np.array([0.1, 0.2]))


def test_benjamini_hochberg_matches_hand_worked_example() -> None:
    # sorted thresholds at alpha=0.05, m=5: 0.01, 0.02, 0.03, 0.04, 0.05
    # sorted p-values:                      0.01, 0.02, 0.03, 0.04, 0.50
    # p <= threshold:                        T,    T,    T,    T,    F
    # largest surviving index = 3 -> first four (sorted) are significant
    p_values = [0.01, 0.02, 0.03, 0.04, 0.5]

    result = benjamini_hochberg(p_values, alpha=0.05)

    assert result == [True, True, True, True, False]


def test_benjamini_hochberg_preserves_input_order() -> None:
    # same five p-values as above, given in a different order
    p_values = [0.04, 0.01, 0.5, 0.02, 0.03]

    result = benjamini_hochberg(p_values, alpha=0.05)

    assert result == [True, True, False, True, True]


def test_benjamini_hochberg_none_significant_when_all_pvalues_are_large() -> None:
    assert benjamini_hochberg([0.9, 0.8, 0.7], alpha=0.05) == [False, False, False]
