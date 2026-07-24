"""財報因子模型持久化（REQ_004：模型訓練與推論流程需可重現，含版本化模型檔案）。

`pickle.loads` 僅還原本系統自己寫入的資料（`model_retrain` 寫入、`weekly_predict` 讀出），
並非反序列化外部/不可信輸入，不構成安全疑慮。
"""

from __future__ import annotations

import datetime as dt
import logging
import pickle

from sqlalchemy.orm import Session

from app.db_models import TrainedModel
from app.prediction.factor_model import FactorModel

logger = logging.getLogger(__name__)

FACTOR_MODEL_NAME = "factor_model"


def save_factor_model(
    session: Session, model: FactorModel, *, version: str, sample_size: int, trained_at: dt.datetime
) -> None:
    artifact = pickle.dumps(model)
    row = session.get(TrainedModel, FACTOR_MODEL_NAME)
    if row is None:
        session.add(
            TrainedModel(
                model_name=FACTOR_MODEL_NAME,
                model_version=version,
                trained_at=trained_at,
                sample_size=sample_size,
                artifact=artifact,
            )
        )
    else:
        row.model_version = version
        row.trained_at = trained_at
        row.sample_size = sample_size
        row.artifact = artifact


def load_factor_model(session: Session) -> FactorModel | None:
    row = session.get(TrainedModel, FACTOR_MODEL_NAME)
    if row is None:
        return None
    try:
        return pickle.loads(row.artifact)
    except Exception:  # noqa: BLE001 - 反序列化失敗不應讓 weekly_predict 整週無法出預測
        logger.exception("model_registry：載入已持久化之財報因子模型失敗，將 fallback 為即時訓練")
        return None
