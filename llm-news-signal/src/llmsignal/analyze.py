"""Entry point for `make analyze`: joins LLM extractions to real forward
returns, tests rank-IC per asset/horizon with Newey-West HAC and
Benjamini-Hochberg correction across all tests run, and runs the
cost-adjusted walk-forward backtest. This is the actual headline result.

Refuses to run at all unless the reliability check
(`reliability_check.run_reliability_check`) passes first - CLAUDE.md's rule
is that extraction reliability must be validated *before* any downstream
claim is trusted, so that has to be an enforced gate here, not a separate
`make reliability` target someone could just forget to run.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from llmsignal.backtest import WalkForwardSplitter, run_backtest
from llmsignal.config import get_settings
from llmsignal.evaluation import max_drawdown, sharpe_ratio
from llmsignal.reliability_check import KAPPA_THRESHOLD, run_reliability_check
from llmsignal.returns.bars import event_time_et_to_utc, forward_return, load_bars
from llmsignal.stats.ic import benjamini_hochberg, rank_ic_newey_west


def _load_joined(asset: str) -> tuple[list[str], list[float], dict[int, list[float]]]:
    """Returns (meeting_dates, scores, {horizon: forward_returns}) for every
    meeting where both an extraction and a full-horizon price window exist.
    """
    settings = get_settings()
    extractions = {r["meeting_date"]: r for r in json.loads(settings.extractions_path.read_text())}
    statement_records = json.loads(settings.fomc_statements_path.read_text())
    statements = {r["meeting_date"]: r for r in statement_records}
    bars = load_bars(settings.bar_paths[asset])

    dates: list[str] = []
    scores: list[float] = []
    returns_by_horizon: dict[int, list[float]] = {h: [] for h in settings.horizons_hours}

    for meeting_date, extraction in sorted(extractions.items()):
        statement = statements[meeting_date]
        event_time = event_time_et_to_utc(meeting_date, statement["release_time_et"])
        horizon_returns = {h: forward_return(bars, event_time, h) for h in settings.horizons_hours}
        if any(r is None for r in horizon_returns.values()):
            continue  # need every horizon available for a fair per-meeting comparison
        dates.append(meeting_date)
        scores.append(extraction["hawkish_dovish_score"])
        for h, r in horizon_returns.items():
            returns_by_horizon[h].append(r)  # type: ignore[arg-type]

    return dates, scores, returns_by_horizon


def main() -> None:
    settings = get_settings()
    if not settings.extractions_path.exists():
        raise SystemExit(
            f"no extractions found at {settings.extractions_path} - run `make extract` first"
        )

    reliability = run_reliability_check(settings.extractions_path, settings.reliability_labels_path)
    if not reliability["passes"]:
        raise SystemExit(
            f"reliability check failed: kappa={reliability['kappa']:.3f} does not clear "
            f"the {KAPPA_THRESHOLD} threshold - run `make reliability` for the full report, "
            "and do not trust an analysis built on unreliable extractions"
        )
    print(f"reliability check passed: kappa={reliability['kappa']:.3f} (n={reliability['n']})")

    all_results: list[dict[str, Any]] = []
    for asset in settings.bar_paths:
        dates, scores, returns_by_horizon = _load_joined(asset)
        scores_arr = np.asarray(scores)
        print(f"\n=== {asset} (n={len(dates)} meetings with full price coverage) ===")
        for horizon in settings.horizons_hours:
            returns = np.asarray(returns_by_horizon[horizon])
            ic_result = rank_ic_newey_west(scores_arr, returns)
            backtest = run_backtest(
                scores_arr, returns, cost_bps=settings.cost_bps, threshold=settings.score_threshold
            )
            _train, test = WalkForwardSplitter(settings.oos_fraction).split(len(dates))
            oos_returns = backtest["net_returns"][test]
            oos_sharpe = sharpe_ratio(oos_returns, periods_per_year=8)
            oos_mdd = max_drawdown(backtest["equity_curve"][test])
            print(
                f"  horizon={horizon:4d}h  ic={ic_result['ic']:+.3f}  "
                f"p={ic_result['p_value']:.3f}  oos_sharpe={oos_sharpe:.2f}  oos_mdd={oos_mdd:.3f}"
            )
            all_results.append(
                {
                    "asset": asset,
                    "horizon_hours": horizon,
                    "n": ic_result["n"],
                    "ic": ic_result["ic"],
                    "p_value": ic_result["p_value"],
                }
            )

    p_values: list[float] = [r["p_value"] for r in all_results]
    significant = benjamini_hochberg(p_values, alpha=0.05)
    print(f"\n=== Benjamini-Hochberg correction across {len(p_values)} tests (alpha=0.05) ===")
    for result, sig in zip(all_results, significant, strict=True):
        flag = "SIGNIFICANT" if sig else "not significant"
        label = f"{result['asset']} {result['horizon_hours']}h"
        print(f"  {label}: p={result['p_value']:.3f} -> {flag}")

    pairs = zip(all_results, significant, strict=True)
    annotated = [{**r, "significant_after_bh": s} for r, s in pairs]
    settings.extractions_path.parent.joinpath("analysis_results.json").write_text(
        json.dumps(annotated, indent=2)
    )


if __name__ == "__main__":
    main()
