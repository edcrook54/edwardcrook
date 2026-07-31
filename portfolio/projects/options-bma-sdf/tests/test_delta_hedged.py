import pytest

from src.returns.delta_hedged import delta_hedged_gain


def test_delta_hedged_gain_not_implemented_yet() -> None:
    # placeholder — replace once delta_hedged_gain is implemented,
    # e.g. test against a hand-computed example from the paper's eq. (5)
    with pytest.raises(NotImplementedError):
        delta_hedged_gain(None, None, None, None)
