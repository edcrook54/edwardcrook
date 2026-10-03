import pytest

from deskagent.config import get_settings
from deskagent.tools.rerun_backtest_variant import rerun_backtest_variant


def _sol_bars_available() -> bool:
    try:
        settings = get_settings()
    except FileNotFoundError:
        return False
    bars_path = settings.showcase_root / "pm-bayes-pricer" / "data" / "bars" / "SOL_1m.parquet"
    return bars_path.exists()


def test_rejects_an_unknown_asset() -> None:
    with pytest.raises(ValueError, match="asset must be one of"):
        rerun_backtest_variant("DOGE")


def test_rejects_an_override_key_outside_the_allowlist() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        rerun_backtest_variant("SOL", overrides={"end_year": 2020})


def test_rejects_an_attempt_to_redefine_the_test_window() -> None:
    # first_test_year/start aren't in ALLOWED_OVERRIDE_KEYS - this must be
    # rejected the same way as any other disallowed key, not silently ignored.
    with pytest.raises(ValueError, match="not allowed"):
        rerun_backtest_variant("SOL", overrides={"first_test_year": 2024})


@pytest.mark.slow
@pytest.mark.skipif(
    not _sol_bars_available(),
    reason=(
        "pm-bayes-pricer/data/bars/SOL_1m.parquet not present - that data is gitignored "
        "and not committed anywhere (see llm-news-signal/CLAUDE.md); only available in "
        "this machine's local dev working copy, not in CI or a fresh clone"
    ),
)
def test_real_subprocess_run_against_sol_cached_bars() -> None:
    # A genuine integration test: runs pm-bayes-pricer's real backtest CLI
    # as a subprocess against the real cached SOL bars (smallest dataset),
    # with overrides chosen only to keep it fast (fewer anchors, one
    # horizon), not to touch the train/test boundary.
    result = rerun_backtest_variant(
        "SOL", overrides={"anchor_step_hours": 48, "horizons_days": [1]}
    )

    assert result["asset"] == "SOL"
    assert result["n_contracts"] > 0
    assert "gbm_har" in result["log_loss_by_model"]
    assert all(loss > 0 for loss in result["log_loss_by_model"].values())
