# DAST 動態應用安全測試報告

> 生成日期：2026-07-14 | Phase 04 測試驗證
> 防護等級：中級 (Medium)　適用構面：構面 5（測試階段）、構面 7（系統與資訊完整性）
> 工具：OWASP ZAP **不可用**（本環境無 Java/ZAP 安裝，見下方說明），改以手動腳本針對實際運行中的 `uvicorn` 服務執行等效動態測試

## 一、測試環境

- 以 `python -m uvicorn app.main:app` 啟動真實服務（非 mock），對 `http://127.0.0.1:8234` 發送實際 HTTP 請求
- 認證情境涵蓋：無金鑰、無效金鑰、有效 read 金鑰、有效 admin 金鑰

## 二、測試項目與結果

### 1. HTTP 安全標頭檢查

| 標頭 | 結果 | 說明 |
| :--- | :--- | :--- |
| `X-Content-Type-Options` | ❌ 缺少 | 建議設定為 `nosniff` |
| `X-Frame-Options` | ❌ 缺少 | 本系統無網頁 UI，Clickjacking 風險較低，仍建議設定 `DENY` |
| `Strict-Transport-Security` | ❌ 缺少 | 待 Phase 05 啟用 HTTPS 後一併設定 |
| `Content-Security-Policy` | ❌ 缺少 | 純 JSON API，優先度較低 |
| `Referrer-Policy` | ❌ 缺少 | 建議設定 `no-referrer` |
| `Server` 標頭洩漏框架資訊 | ⚠️ 洩漏 `uvicorn` | 建議 Phase 05 於反向代理層（Nginx）移除或覆寫此標頭 |

**風險評級**：🟡 中低（本系統為純 JSON API，多數瀏覽器安全標頭之風險場景不直接適用，但仍建議於 Phase 05 部署時透過反向代理統一補上，屬縱深防禦）

### 2. 認證繞過與權限測試

| 測試情境 | 預期 | 實際結果 |
| :--- | :--- | :--- |
| 無 `X-API-Key` 呼叫任一端點 | 401 | ✅ 401 |
| 無效/不存在金鑰 | 401 | ✅ 401，且不揭露金鑰是否存在 |
| read scope 呼叫 admin 端點 | 403 | ✅ 403 |
| admin scope 呼叫 read 端點 | 200（admin 應可存取 read 範圍） | ✅ 200（測試涵蓋於 Phase 03 `tests/test_auth.py`） |

### 3. 注入攻擊測試（SQL Injection / XSS）

| 測試情境 | 輸入 | 結果 |
| :--- | :--- | :--- |
| SQL Injection-like ticker | `2330' OR '1'='1` | ✅ `404 Company not found`，無 SQL 錯誤訊息洩漏、無資料異常回傳（SQLAlchemy ORM 參數化查詢阻擋） |
| XSS-like ticker | `<script>alert(1)</script>` | ✅ `404 Not Found`，內容未被反射回應（本系統無 HTML 渲染，XSS 風險本質上不適用） |

### 4. 輸入驗證邊界測試

| 測試情境 | 輸入 | 結果 |
| :--- | :--- | :--- |
| 無效 market 列舉值 | `market=XX` | ✅ `422`，結構化錯誤訊息，未洩漏內部堆疊 |
| 負數分頁參數 | `quarters=-1` | ✅ `422`，Pydantic `ge=1` 邊界檢查生效 |
| 超量分頁參數 | `quarters=99999` | ✅ `422`，Pydantic `le=40` 邊界檢查生效 |
| 無效 admin 任務列舉值 | `task=not_a_real_task`（搭配 read 金鑰） | ✅ `403`（權限檢查優先於任務列舉驗證，避免洩漏可用任務清單給無權限呼叫者） |

### 5. 錯誤處理與資訊洩漏

- 所有錯誤回應皆為結構化 JSON（`{"detail": "..."}`），未觀察到 Python 堆疊追蹤、檔案路徑或內部變數值洩漏。
- 對應資安需求 REQ_SEC_001 與中級檢核構面 5 項次 53（錯誤僅顯示簡短訊息）。

## 三、階段性限制說明

| 項目 | 說明 |
| :--- | :--- |
| OWASP ZAP 完整掃描 | 本環境未安裝 Java/ZAP，無法執行標準化 ZAP Baseline/Full Scan；已以手動腳本針對相同攻擊面（認證繞過、注入、輸入驗證、錯誤洩漏）執行等效測試，惟涵蓋廣度不若 ZAP 完整（如缺主動式爬蟲探索、被動掃描規則庫）。建議 Phase 05 於具備容器化環境時安裝 ZAP 補做正式掃描 |
| HTTPS/TLS 相關標頭 | 本機開發環境無 TLS，待 Phase 05 部署後於反向代理層一併設定安全標頭 |

## 四、風險與改善建議

| 風險等級 | 項目 | 改善建議 | 預計完成階段 |
| :--------: | :--- | :--- | :--- |
| 🟡 中低 | 缺少 HTTP 安全標頭 | Phase 05 於 Nginx 反向代理設定 `X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、`Strict-Transport-Security` | Phase 05 |
| 🟢 低 | `Server` 標頭洩漏 uvicorn 版本資訊 | Phase 05 於反向代理層移除/覆寫 `Server` 標頭 | Phase 05 |

**結論**：核心攻擊面（認證繞過、SQL Injection、輸入驗證邊界、錯誤資訊洩漏）測試皆無 Critical/High 風險發現；僅存在 2 項中低/低風險之縱深防禦改善項目，皆已排入 Phase 05 部署階段處理。
