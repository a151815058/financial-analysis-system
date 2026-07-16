"""環境設定（T-01）。所有外部服務金鑰一律從環境變數讀取，不寫死於程式碼。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./financial_analysis.db")
    alpha_vantage_api_key: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    sec_edgar_user_agent: str = os.getenv(
        "SEC_EDGAR_USER_AGENT", "financial-analysis-system contact@example.com"
    )
    mops_base_url: str = os.getenv("MOPS_BASE_URL", "https://mopsov.twse.com.tw")
    http_timeout_seconds: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
    http_max_retries: int = int(os.getenv("HTTP_MAX_RETRIES", "3"))
    min_security_score_pct: int = int(os.getenv("MIN_SECURITY_SCORE_PCT", "70"))
    # REQ_014：/admin 頁面帳號密碼登入之 session cookie。正式環境務必由環境變數提供
    # SESSION_SECRET_KEY（render.yaml 使用 generateValue 自動產生），預設值僅供本機開發使用。
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "dev-only-insecure-secret-change-me")
    session_cookie_secure: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
