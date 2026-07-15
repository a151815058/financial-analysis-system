# 安全趨勢報告 (Security Trend Report)

> 生成日期：2026-07-15 | Phase 06 維護與營運
> 觸發原因：`hotfix_log.md` 記錄之 3 項熱修補後，依 SKILL.md 規範強制執行安全回歸檢查

## 一、歷次分數趨勢

| 階段 | 檢查日期 | 分數 | 說明 |
| :--- | :--- | :---: | :--- |
| 03_implementation_and_coding | 2026-07-14 | 100% | SAST + 依賴掃描皆通過 |
| 04_testing | 2026-07-14 | 100% | DAST 等效測試（ZAP 環境不可用，改手動測試） |
| 05_deployment | 2026-07-14 | 90% | 部署安全子項（TLS/Secret 管理/網路隔離），已達 70% 門檻 |
| **06_maintenance（本次）** | **2026-07-15** | **100%** | 見下方細節 |

**趨勢判定**：本次 100% 相較上次（Phase 05 的 90%，但兩者評分範疇不同，Phase 05 為部署安全子項、本次為 SAST+依賴掃描）與 Phase 03/04 的 SAST+依賴掃描基準（100%）持平，**未下降超過 10%**，未觸發 B 類錯誤升級。

## 二、本次掃描方式說明（重要：與框架預設腳本不同）

框架提供之 `scripts/security/run_security_scan.py` 在本環境執行時會失敗：其以裸指令 `bandit`/`pip-audit` 呼叫外部程式，但本機環境僅有 `python -m bandit`/`python -m pip_audit` 可用，導致 `FileNotFoundError` 被腳本內部歸類為 `status: "skip"` 並計入整體 `PASS`，形同**完全沒有實際掃描卻回報通過**。此瑕疵已記錄於框架根目錄 `待辦事項.md` #8，依專案規則不直接修改框架腳本，改為本次手動以 `python -m` 方式執行等效掃描。

## 三、SAST（Bandit）結果

```
python -m bandit -r app -f json -ll -q
```

| 項目 | 結果 |
| :--- | :--- |
| HIGH 嚴重度問題 | 0 |
| MEDIUM 嚴重度問題 | 0 |
| 掃描範圍 | `app/`（含本次新增/修改之 `mops_client.py`、`sec_edgar_client.py`、`alpha_vantage_client.py`、`twse_price_client.py`） |
| 結果 | ✅ PASS（真實執行，非跳過） |

## 四、依賴掃描（pip-audit）結果

```
python -m pip_audit --format json
```

直接執行會涵蓋整個共用 Python 環境（含框架其他工具之相依套件），出現 1 筆與本專案無關的誤報：

| 套件 | 版本 | 漏洞 | 說明 |
| :--- | :--- | :--- | :--- |
| `pillow` | 12.2.0 | 5 筆 CVE（解壓縮炸彈防護繞過、命令注入等，均於 12.3.0 修復） | **非本專案依賴**——`requirements.txt` 未列此套件，實際由環境中另一套件 `python-pptx`（框架 PPTX 技能所需，與本財務分析系統無關）引入。已排除於本專案風險評估範圍外 |

改以 `requirements.txt` 實際列出之 21 個直接相依套件進行過濾比對（`pip-audit -r requirements.txt` 因本機 locale 導致 UnicodeDecodeError 無法直接執行，改以全環境掃描結果手動過濾）：

| 項目 | 結果 |
| :--- | :--- |
| 本專案實際相依套件數 | 21 |
| 其中含已知漏洞 | **0** |
| 結果 | ✅ PASS |

## 五、本次熱修補未新增外部依賴

HF-001/002/003 三項熱修補（詳見 `hotfix_log.md`）皆為既有模組內部邏輯修正，未新增任何第三方套件，`requirements.txt` 無變動，供應鏈風險面未擴大。

## 六、結論

| 檢核項目 | 結果 |
| :--- | :---: |
| SAST（Bandit） | ✅ PASS（0 HIGH/MEDIUM） |
| 依賴掃描（專案實際範圍） | ✅ PASS（0 已知漏洞） |
| 歷史分數比對 | ✅ 未下降超過 10% |
| 安全關卡門檻（`min_security_score_pct=70`） | ✅ 100% ≥ 70% |

本次維護變更之安全回歸檢查通過，無 A 類或 B 類安全錯誤。
