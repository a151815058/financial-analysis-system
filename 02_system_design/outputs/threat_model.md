# 威脅建模 (Threat Model)

> 生成日期：2026-07-14 | Phase 02 系統設計
> 防護等級：中級 (Medium)　適用構面：構面 1（存取控制）、構面 4（識別與鑑別）、構面 6（系統與通訊保護）
> 對應參考：`external-resources/Security-Principles/references/01_access_control.md`、`04_auth.md`、`06_comm_protection.md`
> 方法：STRIDE

## 一、資產清單

| 資產 | 說明 | 敏感度 |
| :--- | :--- | :--- |
| `api_keys.key_hash` | API 存取憑證 | 高 |
| `financial_reports` / `price_history` | 財務與股價資料（多為公開來源） | 中（來源公開，但完整性需保護） |
| `predictions` | 系統預測結果與模型明細 | 中～高（可被視為具商業價值之衍生分析） |
| 外部資料源憑證（SEC EDGAR / Alpha Vantage API Key） | 第三方服務存取金鑰 | 高 |

## 二、STRIDE 威脅分析

| 類別 | 威脅情境 | 影響 | 對應措施 | 構面 |
| :--- | :--- | :--- | :--- | :--- |
| **S**poofing（偽冒） | 攻擊者竊取或猜測 API Key 冒充合法使用者 | 未授權存取財務分析結果 | API Key 以雜湊儲存、金鑰長度 ≥256bit、可撤銷（`revoked_at`） | 構面 1、4 |
| **T**ampering（竄改） | 攻擊者竄改外部資料源回傳內容（如 MOPS 頁面被中間人竄改） | 模型基於錯誤資料訓練/推論，預測失真 | 強制 HTTPS 存取外部資料源、資料驗證與異常值偵測（Phase 04 落實） | 構面 6、7（跨階段） |
| **R**epudiation（否認） | 管理員觸發模型重訓或資料擷取後否認曾執行 | 無法追責 | 所有 admin 動作寫入 `audit_logs`（含 api_key_id、時間戳） | 構面 2（Phase 03/06 落實） |
| **I**nformation Disclosure（資訊洩漏） | API 回應洩漏其他使用者查詢範圍以外之資料，或錯誤訊息洩漏系統內部細節 | 資訊洩漏、攻擊面擴大 | 錯誤回應統一格式，不回傳堆疊追蹤；查詢僅回傳授權範圍內資料 | 構面 1 |
| **D**enial of Service（阻斷服務） | 大量請求打向查詢 API 或觸發大量排程任務 | 服務不可用，影響其他使用者 | Rate Limiting（依 API Key）、admin 端點與 read 端點分離限流策略 | 構面 6（跨階段延伸至 Phase 05 部署） |
| **E**levation of Privilege（權限提升） | read scope 金鑰被用於呼叫 admin 端點 | 未授權觸發排程/重訓任務 | 伺服器端強制檢查 scope，非僅前端限制；預設最小權限（新建金鑰預設 read） | 構面 1、4 |

## 三、外部資料源相關風險（本系統特有）

| 風險 | 說明 | 緩解措施 |
| :--- | :--- | :--- |
| MOPS 網頁結構變更 | 爬取邏輯可能因網站改版而失效或誤讀資料 | Phase 04 需針對資料格式做 Schema 驗證測試，異常時阻斷寫入而非靜默接受錯誤資料 |
| SEC EDGAR XBRL 解析錯誤 | 不同公司申報格式細節差異可能導致欄位對應錯誤 | 建立欄位對應白名單與單元測試（對應 OI-002，Phase 03 落實） |
| Alpha Vantage 速率限制 | 免費層級請求頻率受限，過量請求可能導致資料延遲或服務中斷 | 排程分散請求時間、加入重試與退避機制（REQ_008） |

## 三之一、REQ_011 新增公司端點威脅分析（out-of-band，2026-07-15 追加）

| 類別 | 威脅情境 | 影響 | 對應措施 | 構面 |
| :--- | :--- | :--- | :--- | :--- |
| **T**ampering / Injection | 使用者於 `name`/`industry`/`ticker` 欄位輸入惡意內容 | 資料完整性受損、下游顯示層需正確跳脫 | Pydantic Schema 型別驗證；前端渲染時以 `escapeHtml` 跳脫（沿用既有 `dashboard.js` 作法），不使用字串拼接寫入 SQL（ORM 參數化查詢） | 構面 7 |
| **E**levation of Privilege | `read` scope 金鑰呼叫新增端點 | 未授權寫入公司主檔 | 沿用既有 `require_admin_scope` 依賴，伺服器端強制檢查 | 構面 1、4 |
| SSRF（CIK 自動查詢） | 若查詢 URL 可被使用者輸入操控 | 可能被利用發起任意內部/外部請求 | 查詢 URL 為程式碼內固定白名單常數（`https://www.sec.gov/files/company_tickers.json`），不接受任何使用者輸入拼接 | 構面 6 |
| 重複/競態寫入 | 短時間內重複送出相同公司 | 資料重複或競態條件下違反唯一性 | DB 層 `UNIQUE (market, ticker)` constraint 為最終把關，應用層 409 檢查僅為友善錯誤訊息 | 構面 7 |

## 三之二、REQ_014 帳號密碼登入威脅分析（out-of-band，2026-07-15 追加）

| 類別 | 威脅情境 | 影響 | 對應措施 | 構面 |
| :--- | :--- | :--- | :--- | :--- |
| **S**poofing | 攻擊者暴力猜測帳號密碼 | 冒充後台管理者 | bcrypt 雜湊本身計算成本提供一定防禦；**已知限制**：尚未實作登入失敗節流/帳號鎖定，見 `security_requirements.md` §五之二 | 構面 1、4 |
| **T**ampering / Session hijack | 竊取 session cookie 後冒用登入狀態 | 未授權操作排程 | Session cookie 設 `httponly`（防 JS 竊取）、正式環境 `secure`（僅 HTTPS 傳輸）、`same_site=lax`（防 CSRF 跨站夾帶）、8 小時效期到期即失效 | 構面 6 |
| **I**nformation Disclosure | 登入錯誤訊息洩漏帳號是否存在 | 便於攻擊者列舉有效帳號 | 帳號不存在與密碼錯誤一律回同一句「帳號或密碼錯誤」 | 構面 1 |
| **T**ampering | 密碼於傳輸/儲存過程外洩 | 帳號被冒用 | 密碼雜湊（bcrypt，含 salt）儲存，明文不落地；傳輸仰賴既有 HTTPS 要求（見四、階段性限制說明） | 構面 6、7 |
| **E**levation of Privilege | 一般 read scope API Key 誤用於呼叫 `/api/v1/admin/*` | 未授權觸發排程 | `require_admin_access` 仍檢查 API Key 之 admin scope（未通過回 403），與 session 登入並存但不互相降低門檻 | 構面 1、4 |

## 四、階段性限制說明

- 本機開發環境暫未配置正式 TLS 憑證，構面 6 之 HTTPS 要求於 Phase 05 部署至正式環境後方能完整驗證，屬**階段性限制**，非設計缺陷。
- Rate Limiting 之實際基礎設施（如 API Gateway 層限流）將於 Phase 03/05 落實，本文件僅定義需求與威脅對應關係。
