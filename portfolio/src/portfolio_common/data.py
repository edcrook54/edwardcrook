"""Generic data fetch/cache helpers shared across projects.

Each project's own `src/data/` module should handle project-specific
ingestion (e.g. options chains from Polygon for the BMA-SDF project) and
call into these helpers for the boring, repeated parts: caching to disk,
consistent date handling, etc.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"


def cached_read_parquet(key: str) -> pd.DataFrame | None:
    """Return a cached DataFrame if present, else None."""
    path = CACHE_DIR / f"{key}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return None


def cache_write_parquet(df: pd.DataFrame, key: str) -> None:
    """Write a DataFrame to the shared local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_DIR / f"{key}.parquet")
