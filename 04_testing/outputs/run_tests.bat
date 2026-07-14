@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo  各公司各季度財務分析與股價預測系統 — 一鍵測試執行
echo ============================================================
echo.
echo [1/3] 執行單元測試 + 系統整合測試（共 58 項，含覆蓋率分析）...
echo.

pushd "..\..\03_implementation_and_coding\outputs"
python -m pytest tests "%~dp0test_api.py" --cov=app --cov-report=term-missing --cov-report=json:coverage.json --junitxml="%~dp0combined_test_results.xml" -v
set TEST_EXIT_CODE=%ERRORLEVEL%

if exist "coverage.json" (
    copy /y "coverage.json" "%~dp0coverage.json" >nul 2>&1
)
popd

echo.
echo [2/3] 測試結果摘要（詳見 test_results.md）
echo.

if %TEST_EXIT_CODE% EQU 0 (
    echo ✅ 全部測試通過
) else (
    echo ❌ 有測試失敗，請查看上方輸出與 combined_test_results.xml
)

echo.
echo [3/3] 開啟測試結果報告...
start "" "%~dp0test_results.md"

echo.
echo 完成。
pause
