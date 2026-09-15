from datetime import datetime

import polars as pl

from src.data.alignment import CalendarAligner


def _bars(timestamps, prices):
    return pl.DataFrame({"timestamp": timestamps, "close": prices})


def test_align_backward_fills_onto_grid():
    a = _bars(
        [datetime(2024, 1, 1, 0), datetime(2024, 1, 1, 3), datetime(2024, 1, 1, 6)],
        [10.0, 11.0, 12.0],
    )
    b = _bars(
        [datetime(2024, 1, 1, 1), datetime(2024, 1, 1, 4)],
        [100.0, 110.0],
    )

    aligner = CalendarAligner(freq="1h")
    aligned = aligner.align({"A": a, "B": b})

    # Grid rows before both assets have a bar should be dropped.
    assert aligned["timestamp"].min() >= datetime(2024, 1, 1, 1)
    # Backward-fill means the value at 02:00 should equal the last known bar (01:00 for B).
    row = aligned.filter(pl.col("timestamp") == datetime(2024, 1, 1, 2))
    assert row["B_price"].item() == 100.0


def test_align_produces_return_columns():
    a = _bars([datetime(2024, 1, 1, 0), datetime(2024, 1, 1, 2)], [10.0, 20.0])
    b = _bars([datetime(2024, 1, 1, 0), datetime(2024, 1, 1, 2)], [5.0, 5.0])

    aligned = CalendarAligner(freq="1h").align({"A": a, "B": b})
    assert "A_return" in aligned.columns
    assert "B_return" in aligned.columns
