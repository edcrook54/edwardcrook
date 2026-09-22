"""Fit the live model artifact from tick history: ``python -m pmq.crypto.train``."""

from __future__ import annotations

import argparse
from pathlib import Path

from pmq.config import get_settings
from pmq.crypto import ticks
from pmq.crypto.backtest import load_config
from pmq.crypto.grid import build_hourly_grid
from pmq.crypto.live import fit_artifact


def main() -> None:
    parser = argparse.ArgumentParser(prog="pmq.crypto.train")
    parser.add_argument("--config", default="config/btc.yaml")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    settings = get_settings()
    cache = settings.bars_dir / f"{cfg.asset}_1m.parquet"
    if not cache.exists():
        ticks.build_bar_cache(settings.ticks_dir / f"{cfg.asset}USD.csv", cache)
    grid = build_hourly_grid(ticks.load_bars(cache), start=cfg.start)
    last = str(grid.timestamp(len(grid) - 1))
    artifact = fit_artifact(grid, cfg.asset, trained_through=last)
    out = Path(args.out or f"models/har_{cfg.asset}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    artifact.save(out)
    print(f"wrote {out}  id={artifact.model_id}  trained through {last}")


if __name__ == "__main__":
    main()
