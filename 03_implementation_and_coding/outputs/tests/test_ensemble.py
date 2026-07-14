from __future__ import annotations

import pytest

from app.prediction.ensemble import combine
from app.prediction.factor_model import FactorModelResult
from app.prediction.timeseries_model import TimeSeriesModelResult


def test_combine_keeps_submodel_details():
    factor = FactorModelResult(direction="UP", range_lower_pct=2.0, range_upper_pct=5.0, confidence_score=0.8)
    ts = TimeSeriesModelResult(direction="UP", range_lower_pct=1.0, range_upper_pct=4.0, confidence_score=0.6)

    result = combine(factor, ts)

    assert result.direction == "UP"
    assert result.factor_model is factor
    assert result.timeseries_model is ts
    assert result.weight_factor == 0.6 and result.weight_timeseries == 0.4


def test_combine_range_is_weighted_average():
    factor = FactorModelResult(direction="UP", range_lower_pct=2.0, range_upper_pct=6.0, confidence_score=0.8)
    ts = TimeSeriesModelResult(direction="UP", range_lower_pct=2.0, range_upper_pct=6.0, confidence_score=0.8)

    result = combine(factor, ts, weight_factor=0.5, weight_timeseries=0.5)

    assert result.range_lower_pct == 2.0
    assert result.range_upper_pct == 6.0
    assert result.confidence_score == 0.8  # 方向一致，不打折


def test_combine_reduces_confidence_on_direction_disagreement():
    factor = FactorModelResult(direction="UP", range_lower_pct=2.0, range_upper_pct=5.0, confidence_score=0.8)
    ts = TimeSeriesModelResult(
        direction="DOWN", range_lower_pct=-3.0, range_upper_pct=-1.0, confidence_score=0.7
    )

    result = combine(factor, ts)

    naive_avg = round(0.8 * 0.6 + 0.7 * 0.4, 3)
    assert result.confidence_score < naive_avg


def test_combine_rejects_invalid_weights():
    factor = FactorModelResult(direction="UP", range_lower_pct=2.0, range_upper_pct=5.0, confidence_score=0.8)
    ts = TimeSeriesModelResult(direction="UP", range_lower_pct=1.0, range_upper_pct=4.0, confidence_score=0.6)

    with pytest.raises(ValueError):
        combine(factor, ts, weight_factor=0.7, weight_timeseries=0.7)
