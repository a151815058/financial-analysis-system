"""股價時間序列模型（REQ_005）：以 ARIMA 捕捉短期價格動能，輸出格式與 factor_model 相容。

缺值處理：歷史股價序列以交易日缺漏（假日/停牌）為主，採前值遞補（forward-fill）後
再建模，避免非交易日造成的假性缺口影響 ARIMA 差分項估計。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

TRADING_DAYS_PER_WEEK = 5
DEFAULT_ORDER = (2, 1, 2)
CONFIDENCE_ALPHA = 0.1  # 90% 信賴區間 -> 對應 5%/95% 分位數，與 factor_model 一致


@dataclass(frozen=True)
class TimeSeriesModelResult:
    direction: str
    range_lower_pct: float
    range_upper_pct: float
    confidence_score: float


def fill_missing_trading_days(price_series: pd.Series) -> pd.Series:
    """以前值遞補處理股價序列缺漏（假日/停牌），不得以插值虛構未發生之交易。"""
    return price_series.sort_index().ffill().dropna()


class TimeSeriesModel:
    """以 ARIMA 對單一公司股價序列建模，預測未來一週（TRADING_DAYS_PER_WEEK 個交易日）走勢。"""

    def __init__(self, order: tuple[int, int, int] = DEFAULT_ORDER) -> None:
        self.order = order
        self._fitted_result = None
        self._last_price: float | None = None

    def fit(self, price_series: pd.Series) -> TimeSeriesModel:
        clean_series = fill_missing_trading_days(price_series)
        if len(clean_series) < 30:
            raise ValueError("時間序列模型訓練需至少 30 個交易日之股價資料")

        self._last_price = float(clean_series.iloc[-1])
        model = ARIMA(clean_series.to_numpy(), order=self.order)
        self._fitted_result = model.fit()
        return self

    def predict_next_week(self) -> TimeSeriesModelResult:
        if self._fitted_result is None or self._last_price is None:
            raise RuntimeError("TimeSeriesModel 尚未訓練，請先呼叫 fit()")

        forecast = self._fitted_result.get_forecast(steps=TRADING_DAYS_PER_WEEK)
        mean_forecast = forecast.predicted_mean[-1]
        conf_int = forecast.conf_int(alpha=CONFIDENCE_ALPHA)[-1]

        last_price = self._last_price
        mean_return_pct = (mean_forecast - last_price) / last_price * 100
        lower_return_pct = (conf_int[0] - last_price) / last_price * 100
        upper_return_pct = (conf_int[1] - last_price) / last_price * 100

        direction = "FLAT"
        if mean_return_pct > 1.0:
            direction = "UP"
        elif mean_return_pct < -1.0:
            direction = "DOWN"

        lo, hi = sorted((round(float(lower_return_pct) * 2) / 2, round(float(upper_return_pct) * 2) / 2))
        # 信賴區間寬度轉換為 0~1 信心分數：區間越窄，信心越高
        width = max(hi - lo, 1e-6)
        confidence = float(np.clip(1.0 / (1.0 + width / 10.0), 0.0, 1.0))

        return TimeSeriesModelResult(
            direction=direction,
            range_lower_pct=lo,
            range_upper_pct=hi,
            confidence_score=round(confidence, 3),
        )
