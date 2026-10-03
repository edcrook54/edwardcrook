"""A narrow, sandboxed wrapper around the exact statistical tests
`crypto-cointegration-signal` and `llm-news-signal` already use (ADF,
Engle-Granger, Newey-West HAC mean test) - no arbitrary code execution, just
a dispatch over three named, bounded operations the agent can call.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint

TestName = Literal["adf", "engle_granger", "newey_west_mean"]

VALID_TESTS: tuple[TestName, ...] = ("adf", "engle_granger", "newey_west_mean")


def run_stat_test(
    test: str,
    series_a: list[float],
    series_b: list[float] | None = None,
    maxlags: int = 3,
) -> dict[str, Any]:
    if test not in VALID_TESTS:
        raise ValueError(f"unknown test {test!r}; must be one of {VALID_TESTS}")

    a = np.asarray(series_a, dtype=float)
    if len(a) < 8:
        raise ValueError(f"series_a has only {len(a)} points; need at least 8 for a stable test")

    if test == "adf":
        statistic, p_value, _usedlag, _nobs, critical_values, _icbest = adfuller(
            a, result_object=False
        )
        return {
            "test": "adf",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "critical_values": {k: float(v) for k, v in critical_values.items()},
            "n": len(a),
        }

    if test == "engle_granger":
        if series_b is None:
            raise ValueError("engle_granger requires series_b")
        b = np.asarray(series_b, dtype=float)
        if len(a) != len(b):
            raise ValueError(
                f"series_a and series_b must be the same length ({len(a)} != {len(b)})"
            )
        statistic, p_value, critical_values = coint(a, b)
        return {
            "test": "engle_granger",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "critical_values": {
                "1%": float(critical_values[0]),
                "5%": float(critical_values[1]),
                "10%": float(critical_values[2]),
            },
            "n": len(a),
        }

    # newey_west_mean: is the series' mean significantly different from zero,
    # with a Newey-West HAC-corrected standard error (serially correlated
    # returns violate the IID assumption a naive SE would rely on). A
    # constant-only OLS regression's coefficient is exactly the sample mean;
    # HAC gives it a serial-correlation-robust standard error.
    x = np.ones((len(a), 1))
    model = sm.OLS(a, x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {
        "test": "newey_west_mean",
        "mean": float(a.mean()),
        "t_stat": float(model.tvalues[0]),
        "p_value": float(model.pvalues[0]),
        "n": len(a),
    }
