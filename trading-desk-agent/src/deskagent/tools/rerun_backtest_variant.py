"""Re-runs `pm-bayes-pricer`'s real backtest CLI as a subprocess, with
bounded, whitelisted config overrides, a timeout, and a temp output
directory - the agent can explore "what if" variants of an existing
backtest without being able to execute arbitrary code or touch anything
outside pm-bayes-pricer's own config/output files.

Only hyperparameters that don't redefine the train/test boundary are
overridable (`start`/`first_test_year`/`end_year`/`asset` are fixed by the
base config) - the agent can ask "what if the vol half-life were shorter,"
not "what if the test window were different," which would let it quietly
re-draw its own out-of-sample split.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from deskagent.config import get_settings

ALLOWED_OVERRIDE_KEYS = frozenset(
    {
        "z_grid",
        "ewma_half_life_days",
        "bayes_memory_days",
        "min_coverage",
        "horizons_days",
        "n_quadrature",
        "anchor_step_hours",
    }
)

_ASSET_TO_CONFIG = {"BTC": "btc", "ETH": "eth", "SOL": "sol"}
_ASSET_TO_PARQUET_PREFIX = {"BTC": "XBT", "ETH": "ETH", "SOL": "SOL"}

MODELS = (
    "naive_2x",
    "gbm_trailing30",
    "gbm_rv7",
    "gbm_ewma",
    "gbm_har",
    "bayes_disc",
    "har_mix",
    "har_mix_recal",
    "base_rate",
)


def _log_loss(p: pd.Series, y: pd.Series) -> float:
    eps = 1e-9
    p_clipped = p.clip(eps, 1 - eps)
    losses = y * np.log(p_clipped) + (1 - y) * np.log(1 - p_clipped)
    return float(-losses.mean())


def rerun_backtest_variant(asset: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    if asset not in _ASSET_TO_CONFIG:
        raise ValueError(f"asset must be one of {sorted(_ASSET_TO_CONFIG)}, got {asset!r}")
    overrides = overrides or {}
    bad_keys = set(overrides) - ALLOWED_OVERRIDE_KEYS
    if bad_keys:
        raise ValueError(f"these override keys are not allowed: {sorted(bad_keys)}")

    settings = get_settings()
    pm_root = settings.showcase_root / "pm-bayes-pricer"
    base_config_path = pm_root / "config" / f"{_ASSET_TO_CONFIG[asset]}.yaml"
    base_config: dict[str, Any] = yaml.safe_load(base_config_path.read_text())
    merged_config = {**base_config, **overrides}

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.safe_dump(merged_config))
        out_dir = tmp_path / "outputs"

        python = pm_root / ".venv" / "bin" / "python"
        result = subprocess.run(
            [
                str(python if python.exists() else sys.executable),
                "-m",
                "pmq.crypto.backtest",
                "--config",
                str(config_path),
                "--out",
                str(out_dir),
            ],
            cwd=pm_root,
            capture_output=True,
            text=True,
            timeout=settings.tool_timeout_seconds,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"backtest subprocess failed (exit {result.returncode}): {result.stderr[-2000:]}"
            )

        parquet_path = out_dir / f"backtest_{_ASSET_TO_PARQUET_PREFIX[asset]}.parquet"
        df = pd.read_parquet(parquet_path)

    log_loss_by_model = {
        model: _log_loss(df[model], df["label"]) for model in MODELS if model in df.columns
    }
    return {
        "asset": asset,
        "overrides_applied": overrides,
        "n_contracts": len(df),
        "log_loss_by_model": log_loss_by_model,
    }
