# 各公司各季度財務分析與股價預測系統 — 生產環境映像檔
# ⚠️ 本機環境未安裝 Docker，本檔案未經 `docker build` 實際驗證，見 deployment_topology.md「驗證限制」

FROM python:3.12-slim AS base

# 系統套件：lxml/psycopg 編譯期需要；curl 供 HEALTHCHECK 使用
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY 03_implementation_and_coding/outputs/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY 03_implementation_and_coding/outputs/app ./app

# 🔒 非 root 使用者執行（構面 1：最小權限原則）
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
