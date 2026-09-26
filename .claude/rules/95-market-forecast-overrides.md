# Market Forecast 專案覆寫

本檔只覆寫從 Kaledoxa baseline 繼承、但具有產品專屬語義的部分；未覆寫的治理規則照原 baseline 生效。

## Product boundaries

目前 bounded capabilities：

- `market_data`：市場資料來源、canonical bars、security/session identity。
- `realized_variance`：intraday aggregation、overnight、RV/RQ/semivariance measurement。
- `risk_forecast`：GARCH/HAR/HARQ/Ridge-HAR fitting 與 frozen model。
- `forecast_validation`：chronological split、purge、QLIKE、bootstrap、promotion/stop gates。
- `runtime_ops`：CLI/composition delivery track，不是 domain authority。

## 不適用的 Kaledoxa-specific 規則

任何只針對 Camoufox、Playwright、social providers、clinic/news/triage/knowledge、OpenAPI HTTP product、frontend sibling repo 的要求，在本專案沒有對應 Task/spec 時不構成產品需求。

安全、Git、測試、文件、ports/adapters、DTO、DI、Task-local readiness 與 human-readable GitHub records 等通用治理仍生效。

## Data / research side effects

下載付費或有 quota 的 market data、bulk backfill、provider API call、覆蓋 raw data、重新 freeze universe/model，都視為具副作用操作；必須有 Task 明示授權並記錄 provenance。
