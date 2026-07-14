from __future__ import annotations

import pytest

from app.prediction.backtest import BacktestRecord, summarize


def test_direction_and_range_hit_true_case():
    r = BacktestRecord(
        predicted_direction="UP", range_lower_pct=2.0, range_upper_pct=5.0, actual_return_pct=3.0
    )
    assert r.actual_direction == "UP"
    assert r.direction_hit is True
    assert r.range_hit is True


def test_direction_hit_false_when_wrong_direction():
    r = BacktestRecord(
        predicted_direction="UP", range_lower_pct=2.0, range_upper_pct=5.0, actual_return_pct=-3.0
    )
    assert r.actual_direction == "DOWN"
    assert r.direction_hit is False


def test_range_hit_false_when_outside_bounds():
    r = BacktestRecord(
        predicted_direction="UP", range_lower_pct=2.0, range_upper_pct=5.0, actual_return_pct=8.0
    )
    assert r.direction_hit is True  # 方向仍正確
    assert r.range_hit is False  # 但幅度超出區間


def test_summarize_computes_rates():
    records = [
        BacktestRecord("UP", 2.0, 5.0, 3.0),  # 方向對、區間對
        BacktestRecord("UP", 2.0, 5.0, -1.0),  # 方向錯
        BacktestRecord("DOWN", -5.0, -2.0, -3.0),  # 方向對、區間對
        BacktestRecord("UP", 2.0, 5.0, 8.0),  # 方向對、區間錯
    ]
    summary = summarize(records)
    assert summary.window_weeks == 4
    assert summary.directional_accuracy == 0.75
    assert summary.range_hit_rate == 0.5


def test_summarize_raises_on_empty_records():
    with pytest.raises(ValueError):
        summarize([])
