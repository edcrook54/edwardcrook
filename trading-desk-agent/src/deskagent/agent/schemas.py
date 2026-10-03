"""Tool schemas (Anthropic tool-use format) for the four sandboxed tools.
Kept here, separate from the tool implementations themselves, so the
contract the model sees is reviewable in one place.
"""

from __future__ import annotations

from typing import Any

SEARCH_CORPUS_SCHEMA: dict[str, Any] = {
    "name": "search_corpus",
    "description": (
        "Search the quant-research corpus (crypto-cointegration-signal and "
        "pm-bayes-pricer's READMEs, AUDIT.md, CLAUDE.md, notebooks, configs) via "
        "trading-research-rag's live retrieval service. Returns ranked hits with "
        "exact citations - always cite the returned `citation` field, never guess one."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            "mode": {"type": "string", "enum": ["bm25", "dense", "hybrid"], "default": "hybrid"},
        },
        "required": ["query"],
    },
}

RUN_STAT_TEST_SCHEMA: dict[str, Any] = {
    "name": "run_stat_test",
    "description": (
        "Run one of three statistical tests on numeric series you already have "
        "(e.g. from a prior tool result): 'adf' (unit-root/stationarity test on "
        "series_a), 'engle_granger' (cointegration test between series_a and "
        "series_b), or 'newey_west_mean' (is series_a's mean significantly "
        "different from zero, with a serial-correlation-robust standard error)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "test": {"type": "string", "enum": ["adf", "engle_granger", "newey_west_mean"]},
            "series_a": {"type": "array", "items": {"type": "number"}},
            "series_b": {"type": "array", "items": {"type": "number"}},
            "maxlags": {"type": "integer", "minimum": 1, "default": 3},
        },
        "required": ["test", "series_a"],
    },
}

RERUN_BACKTEST_VARIANT_SCHEMA: dict[str, Any] = {
    "name": "rerun_backtest_variant",
    "description": (
        "Re-run pm-bayes-pricer's real backtest for BTC, ETH, or SOL with bounded "
        "hyperparameter overrides (z_grid, ewma_half_life_days, bayes_memory_days, "
        "min_coverage, horizons_days, n_quadrature, anchor_step_hours). The "
        "train/test split itself cannot be changed. Takes up to a minute; use "
        "sparingly, and prefer small, targeted overrides."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset": {"type": "string", "enum": ["BTC", "ETH", "SOL"]},
            "overrides": {"type": "object"},
        },
        "required": ["asset"],
    },
}

GET_FILE_SCHEMA: dict[str, Any] = {
    "name": "get_file",
    "description": (
        "Read a file's full contents, e.g. 'pm-bayes-pricer/README.md' or "
        "'crypto-cointegration-signal/AUDIT.md'. Restricted to the showcase "
        "projects; capped at 200KB per file."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"relative_path": {"type": "string"}},
        "required": ["relative_path"],
    },
}

ALL_TOOL_SCHEMAS: list[dict[str, Any]] = [
    SEARCH_CORPUS_SCHEMA,
    RUN_STAT_TEST_SCHEMA,
    RERUN_BACKTEST_VARIANT_SCHEMA,
    GET_FILE_SCHEMA,
]
