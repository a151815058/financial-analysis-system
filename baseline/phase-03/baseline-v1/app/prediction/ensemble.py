"""雙模型融合（REQ_006）：財報因子模型 + 時間序列模型 Ensemble，保留子模型明細供可解釋性追溯。"""

from __future__ import annotations

from dataclasses import dataclass

from app.prediction.factor_model import FactorModelResult
from app.prediction.timeseries_model import TimeSeriesModelResult

DEFAULT_WEIGHT_FACTOR = 0.6
DEFAULT_WEIGHT_TIMESERIES = 0.4
_DIRECTION_SCORE = {"DOWN": -1, "FLAT": 0, "UP": 1}
_SCORE_DIRECTION = {-1: "DOWN", 0: "FLAT", 1: "UP"}


@dataclass(frozen=True)
class EnsembleResult:
    direction: str
    range_lower_pct: float
    range_upper_pct: float
    confidence_score: float
    factor_model: FactorModelResult
    timeseries_model: TimeSeriesModelResult
    weight_factor: float
    weight_timeseries: float


def _weighted_direction(
    factor_direction: str, ts_direction: str, weight_factor: float, weight_timeseries: float
) -> str:
    score = (
        _DIRECTION_SCORE[factor_direction] * weight_factor
        + _DIRECTION_SCORE[ts_direction] * weight_timeseries
    )
    if score > 0.2:
        return "UP"
    if score < -0.2:
        return "DOWN"
    return "FLAT"


def combine(
    factor_result: FactorModelResult,
    timeseries_result: TimeSeriesModelResult,
    weight_factor: float = DEFAULT_WEIGHT_FACTOR,
    weight_timeseries: float = DEFAULT_WEIGHT_TIMESERIES,
) -> EnsembleResult:
    if not abs(weight_factor + weight_timeseries - 1.0) < 1e-6:
        raise ValueError("weight_factor + weight_timeseries 必須等於 1.0")

    direction = _weighted_direction(
        factor_result.direction, timeseries_result.direction, weight_factor, weight_timeseries
    )
    range_lower = round(
        factor_result.range_lower_pct * weight_factor + timeseries_result.range_lower_pct * weight_timeseries,
        3,
    )
    range_upper = round(
        factor_result.range_upper_pct * weight_factor + timeseries_result.range_upper_pct * weight_timeseries,
        3,
    )
    if range_lower > range_upper:
        range_lower, range_upper = range_upper, range_lower

    confidence = round(
        factor_result.confidence_score * weight_factor
        + timeseries_result.confidence_score * weight_timeseries,
        3,
    )
    # 兩子模型方向不一致時，降低最終信心分數以反映不確定性
    if factor_result.direction != timeseries_result.direction:
        confidence = round(confidence * 0.8, 3)

    return EnsembleResult(
        direction=direction,
        range_lower_pct=range_lower,
        range_upper_pct=range_upper,
        confidence_score=confidence,
        factor_model=factor_result,
        timeseries_model=timeseries_result,
        weight_factor=weight_factor,
        weight_timeseries=weight_timeseries,
    )
