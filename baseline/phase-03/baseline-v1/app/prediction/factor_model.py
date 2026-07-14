"""財報因子統計模型（REQ_004），解決 OI-003：預測幅度區間採統計分位數估計。

OI-003 決議：不採固定級距（如「2% 一級距」），改以 statsmodels 分位數迴歸（Quantile
Regression）估計未來一週報酬率的 5% / 95% 分位數作為幅度區間上下限，四捨五入至最近
0.5%。相較固定級距，此法依實際資料分布給出區間寬度，較具統計依據，且會隨訓練資料更新。

輸入特徵：以正規化後財務指標（及其年增率/環比變化）為特徵；訓練標的：
  - 方向分類（UP/DOWN/FLAT）：由下一週實際報酬率依 ±NEUTRAL_BAND 切分
  - 幅度區間迴歸：下一週實際報酬率（連續值）

模型訓練與推論皆固定 random_state，確保可重現（Phase 01 REQ_004 驗收條件）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import GradientBoostingClassifier

RANDOM_STATE = 42
NEUTRAL_BAND_PCT = 1.0  # 週報酬率絕對值 < 1% 視為 FLAT
LOWER_QUANTILE = 0.05
UPPER_QUANTILE = 0.95


@dataclass(frozen=True)
class FactorModelResult:
    direction: str  # "UP" / "DOWN" / "FLAT"
    range_lower_pct: float
    range_upper_pct: float
    confidence_score: float


def label_direction(weekly_return_pct: pd.Series, neutral_band: float = NEUTRAL_BAND_PCT) -> pd.Series:
    return pd.cut(
        weekly_return_pct,
        bins=[-np.inf, -neutral_band, neutral_band, np.inf],
        labels=["DOWN", "FLAT", "UP"],
    )


class FactorModel:
    """財報因子統計模型：分類器估方向 + 分位數迴歸估幅度區間。"""

    def __init__(self, random_state: int = RANDOM_STATE) -> None:
        self.random_state = random_state
        self._classifier = GradientBoostingClassifier(random_state=random_state)
        self._quantile_models: dict[float, sm.regression.linear_model.RegressionResultsWrapper] = {}
        self._feature_columns: list[str] | None = None
        self._is_fitted = False

    def fit(self, features: pd.DataFrame, weekly_return_pct: pd.Series) -> FactorModel:
        if len(features) < 10:
            raise ValueError("財報因子模型訓練樣本需至少 10 筆，避免過度配適與統計不穩定")

        self._feature_columns = list(features.columns)
        direction_labels = label_direction(weekly_return_pct)
        self._classifier.fit(features, direction_labels)

        design_matrix = sm.add_constant(features, has_constant="add")
        for q in (LOWER_QUANTILE, UPPER_QUANTILE):
            model = sm.QuantReg(weekly_return_pct, design_matrix)
            self._quantile_models[q] = model.fit(q=q, max_iter=2000)

        self._is_fitted = True
        return self

    def predict(self, features: pd.DataFrame) -> list[FactorModelResult]:
        if not self._is_fitted or self._feature_columns is None:
            raise RuntimeError("FactorModel 尚未訓練，請先呼叫 fit()")

        features = features[self._feature_columns]
        direction_pred = self._classifier.predict(features)
        proba = self._classifier.predict_proba(features)
        confidence = proba.max(axis=1)

        design_matrix = sm.add_constant(features, has_constant="add")
        lower = self._quantile_models[LOWER_QUANTILE].predict(design_matrix)
        upper = self._quantile_models[UPPER_QUANTILE].predict(design_matrix)

        results = []
        for i in range(len(features)):
            lo, hi = sorted((round(float(lower.iloc[i]) * 2) / 2, round(float(upper.iloc[i]) * 2) / 2))
            results.append(
                FactorModelResult(
                    direction=str(direction_pred[i]),
                    range_lower_pct=lo,
                    range_upper_pct=hi,
                    confidence_score=round(float(confidence[i]), 3),
                )
            )
        return results
