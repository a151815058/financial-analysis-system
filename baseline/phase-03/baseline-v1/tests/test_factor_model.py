from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.prediction.factor_model import FactorModel, label_direction


def _synthetic_dataset(n: int = 60, seed: int = 42):
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(
        {
            "revenue_yoy": rng.normal(5, 3, n),
            "eps_qoq": rng.normal(0, 2, n),
            "gross_margin": rng.normal(45, 5, n),
        }
    )
    # 報酬率與 revenue_yoy 正相關，模擬「財報因子確實有預測力」的合成情境
    weekly_return_pct = 0.3 * features["revenue_yoy"] + rng.normal(0, 1, n)
    return features, weekly_return_pct


def test_label_direction_thresholds():
    returns = pd.Series([-5.0, -0.5, 0.0, 0.5, 5.0])
    labels = label_direction(returns)
    assert list(labels) == ["DOWN", "FLAT", "FLAT", "FLAT", "UP"]


def test_fit_requires_minimum_samples():
    model = FactorModel()
    features = pd.DataFrame({"a": [1, 2, 3]})
    returns = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        model.fit(features, returns)


def test_predict_output_format_and_range_ordering():
    features, returns = _synthetic_dataset()
    model = FactorModel().fit(features, returns)

    results = model.predict(features.iloc[:5])
    assert len(results) == 5
    for r in results:
        assert r.direction in {"UP", "DOWN", "FLAT"}
        assert r.range_lower_pct <= r.range_upper_pct
        assert 0.0 <= r.confidence_score <= 1.0


def test_predict_is_reproducible_with_fixed_random_state():
    features, returns = _synthetic_dataset()
    model_a = FactorModel(random_state=42).fit(features, returns)
    model_b = FactorModel(random_state=42).fit(features, returns)

    result_a = model_a.predict(features.iloc[:3])
    result_b = model_b.predict(features.iloc[:3])

    assert [r.direction for r in result_a] == [r.direction for r in result_b]
    assert [r.range_lower_pct for r in result_a] == [r.range_lower_pct for r in result_b]
