@echo off
chcp 65001 >nul
REM 啟動財務分析與股價預測系統 API（開發模式，SQLite）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
