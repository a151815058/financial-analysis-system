# 使用案例圖 (Use Case Diagram)

> 生成日期：2026-07-14 | Phase 02 系統設計
> 來源：SSOT `specs/executable_spec.yaml` + `formal_requirements.md`

---

## Mermaid 格式（角色 × 功能矩陣圖）

```mermaid
flowchart LR
    subgraph Actors["👤 角色"]
        USER["🏷️ API 使用者<br/>read scope"]
        ADMIN["🏷️ 系統管理員<br/>admin scope"]
        SCHED["⏰ 排程器<br/>系統內部"]
        MOPS["🔗 公開資訊觀測站<br/>外部系統"]
        EDGAR["🔗 SEC EDGAR<br/>外部系統"]
        AV["🔗 Alpha Vantage<br/>外部系統"]
    end

    subgraph UC_User["API 使用者功能"]
        UC01["📊 查詢公司清單"]
        UC02["📈 查詢財務指標歷史"]
        UC03["💹 查詢股價歷史"]
        UC04["🔮 查詢最新一週預測"]
        UC05["🕰️ 查詢歷史預測"]
        UC06["✅ 查詢回測準確率"]
    end

    subgraph UC_Admin["管理員功能"]
        UC07["▶️ 手動觸發資料擷取"]
        UC08["🔁 手動觸發模型重訓"]
        UC09["🔍 查詢稽核日誌"]
    end

    subgraph UC_System["系統內部功能"]
        UC10["📥 台股財報擷取"]
        UC11["📥 美股財報擷取"]
        UC12["📥 股價資料擷取"]
        UC13["🧮 財報因子模型推論"]
        UC14["📉 時間序列模型推論"]
        UC15["🔗 雙模型融合"]
        UC16["📝 記錄稽核日誌"]
    end

    USER --> UC01
    USER --> UC02
    USER --> UC03
    USER --> UC04
    USER --> UC05
    USER --> UC06

    ADMIN --> UC07
    ADMIN --> UC08
    ADMIN --> UC09
    ADMIN -. "繼承" .-> USER

    SCHED --> UC10
    SCHED --> UC11
    SCHED --> UC12
    SCHED --> UC13
    SCHED --> UC14

    UC10 -.->|HTTP/爬取| MOPS
    UC11 -.->|API| EDGAR
    UC12 -.->|API| AV

    UC13 --> UC15
    UC14 --> UC15
    UC15 -.->|include| UC16
    UC02 -.->|include| UC16
    UC04 -.->|include| UC16
    UC07 -.->|include| UC16
```

---

## 使用案例摘要

| 案例 | 參與者 | 說明 | 對應 REQ |
| :--- | :--- | :--- | :--- |
| UC-01 | API 使用者 | 查詢公司清單（可篩市場/產業） | REQ_003 |
| UC-02 | API 使用者 | 查詢財務指標歷史 | REQ_001/002/003 |
| UC-03 | API 使用者 | 查詢股價歷史 | REQ_005 |
| UC-04 | API 使用者 | 查詢最新一週預測結果 | REQ_004/005/006/007 |
| UC-05 | API 使用者 | 查詢歷史預測結果 | REQ_007 |
| UC-06 | API 使用者 | 查詢回測準確率報告 | REQ_009 |
| UC-07 | 系統管理員 | 手動觸發資料擷取任務 | REQ_008 |
| UC-08 | 系統管理員 | 手動觸發模型重訓 | REQ_008 |
| UC-09 | 系統管理員 | 查詢稽核日誌 | REQ_SEC_001（構面 2） |
| UC-10 | 排程器 | 台股財報擷取（MOPS） | REQ_001 |
| UC-11 | 排程器 | 美股財報擷取（SEC EDGAR） | REQ_002 |
| UC-12 | 排程器 | 股價資料擷取（Alpha Vantage） | REQ_002/005 |
| UC-13 | 排程器 | 財報因子模型推論 | REQ_004 |
| UC-14 | 排程器 | 時間序列模型推論 | REQ_005 |
| UC-15 | 排程器 | 雙模型融合 | REQ_006 |
| UC-16 | 系統 | 自動記錄所有查詢/擷取/推論行為至 audit_log | REQ_SEC_001 |

---

## 角色階層

```
API 使用者 (read)
  └─ 系統管理員 (admin) ← 繼承 read 權限 + 擴充排程觸發與稽核查詢
```
