from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.prediction.timeseries_model import TimeSeriesModel, fill_missing_trading_days


def _synthetic_price_series(n: int = 90, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    prices = 100 + np.cumsum(rng.normal(0.1, 1.0, n))
    return pd.Series(prices, index=dates)


def test_fill_missing_trading_days_forward_fills_gaps():
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    series = pd.Series([100.0, np.nan, 102.0], index=dates)
    filled = fill_missing_trading_days(series)
    assert filled.loc[pd.Timestamp("2026-01-02")] == 100.0  # 前值遞補


def test_fit_requires_minimum_history():
    model = TimeSeriesModel()
    short_series = _synthetic_price_series(n=10)
    with pytest.raises(ValueError):
        model.fit(short_series)


def test_predict_next_week_output_format():
    series = _synthetic_price_series()
    model = TimeSeriesModel().fit(series)
    result = model.predict_next_week()

    assert result.direction in {"UP", "DOWN", "FLAT"}
    assert result.range_lower_pct <= result.range_upper_pct
    assert 0.0 <= result.confidence_score <= 1.0


def test_predict_without_fit_raises():
    model = TimeSeriesModel()
    with pytest.raises(RuntimeError):
        model.predict_next_week()
