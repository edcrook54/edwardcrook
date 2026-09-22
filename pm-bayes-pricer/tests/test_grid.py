import numpy as np
import polars as pl

from pmq.crypto import grid


def _bars(rows):
    return pl.DataFrame(
        {
            "ts": [r[0] for r in rows],
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [1.0] * len(rows),
            "n_trades": [1] * len(rows),
        }
    ).with_columns(pl.col("ts").str.to_datetime(time_zone="UTC"))


def test_sparse_table_matches_brute_force() -> None:
    rng = np.random.default_rng(0)
    v = rng.random(500)
    hi, lo = grid.SparseTable(v, True), grid.SparseTable(v, False)
    starts = rng.integers(0, 400, 300)
    lengths = rng.integers(1, 100, 300)
    highs, lows = hi.query(starts, lengths), lo.query(starts, lengths)
    for s, n, h, low in zip(starts, lengths, highs, lows, strict=True):
        assert h == v[s : s + n].max() and low == v[s : s + n].min()


def test_hourly_grid_keeps_exact_minute_extremes_and_forward_fills_quiet_hours() -> None:
    bars = _bars(
        [
            ("2024-01-01 00:03:00", 100, 101, 99, 100),
            ("2024-01-01 00:40:00", 100, 105, 98, 104),
            # nothing trades during 01:00-01:59
            ("2024-01-01 02:10:00", 104, 106, 103, 105),
        ]
    )
    g = grid.build_hourly_grid(bars)
    assert len(g) == 3
    assert g.high[0] == 105 and g.low[0] == 98  # true extremes of the two minute bars
    assert not g.traded[1] and g.high[1] == -np.inf and g.low[1] == np.inf
    assert g.close[1] == 104  # last known price carried forward
    ex = grid.WindowExtremes(g)
    assert ex.highest(np.array([0]), 3)[0] == 106
    assert ex.lowest(np.array([1]), 2)[0] == 103  # the quiet hour cannot set a low
