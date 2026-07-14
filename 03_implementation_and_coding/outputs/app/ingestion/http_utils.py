"""共用 HTTP 重試工具。三個外部資料擷取模組（MOPS/SEC EDGAR/Alpha Vantage）皆依賴此模組，
確保單一來源逾時或暫時性錯誤不會中斷整批擷取任務（REQ_001/002 驗收條件）。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import requests

from app.config import settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ExternalSourceError(Exception):
    """外部資料來源擷取失敗（已耗盡重試次數）。"""


def get_with_retry(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    max_retries: int | None = None,
    timeout: float | None = None,
    backoff_base_seconds: float = 0.5,
) -> requests.Response:
    """帶指數退避重試的 GET 請求。僅對逾時/5xx/429 重試，4xx（除 429 外）視為不可重試錯誤。"""
    retries = max_retries if max_retries is not None else settings.http_max_retries
    request_timeout = timeout if timeout is not None else settings.http_timeout_seconds

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=request_timeout)
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise ExternalSourceError(f"Retryable HTTP {response.status_code} from {url}")
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError, ExternalSourceError) as exc:
            last_exc = exc
            logger.warning("attempt %s/%s failed for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(backoff_base_seconds * (2 ** (attempt - 1)))

    raise ExternalSourceError(f"Exhausted {retries} retries for {url}") from last_exc


def run_batch_isolated[T](items: list[T], fn: Callable[[T], None]) -> tuple[list[T], list[tuple[T, str]]]:
    """對批次項目逐一執行 fn，單一項目失敗不影響其餘項目（REQ_001/002 核心驗收條件）。

    回傳 (成功項目清單, [(失敗項目, 錯誤訊息), ...])。
    """
    succeeded: list[T] = []
    failed: list[tuple[T, str]] = []
    for item in items:
        try:
            fn(item)
            succeeded.append(item)
        except Exception as exc:  # noqa: BLE001 - 批次擷取需隔離任一項目的例外
            logger.error("batch item failed: %s (%s)", item, exc)
            failed.append((item, str(exc)))
    return succeeded, failed
