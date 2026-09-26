# Context Map

## 目標結構

```text
src/
├── apps/
│   └── cli/
└── libs/
    ├── kernel/
    ├── market_data/
    ├── realized_variance/
    ├── risk_forecast/
    └── forecast_validation/
```

採薄 app、厚 lib。CLI 只做 parsing / composition / transport，不擁有研究規則。

## Bounded capabilities

### market-data

Authority：來源資料與 canonical bar identity。

公開能力：
- 讀取/保存 immutable provider observations
- canonical 1m OHLCV
- session / exchange / symbol identity
- provenance / content hash

不得決定 RV sampling 或模型。

### realized-variance

Authority：ex-post volatility measurement。

公開能力：
- deterministic 1m→5m/10m/15m
- regular-session RV/RQ/semivariance
- overnight squared return
- whole-day variance
- future H-day target construction

不得依 forecast score 選 measurement。

### risk-forecast

Authority：forecast specification / fitting / frozen inference。

模型家族目前限：
- EWMA
- GARCH(1,1)
- HAR / Log-HAR
- pooled Ridge-HAR
- market interaction shrinkage
- HARQ 僅在 measurement lock 後

### forecast-validation

Authority：如何判定研究成立。

- complete-date chronological folds
- H-local-session purge
- symbol-transfer holdout
- final holdout
- QLIKE
- date-block bootstrap
- promotion / stop gate

### runtime-ops

工程 delivery track，不是 BC。擁有 CLI/composition/governance wiring，不接管上列研究規則。

## 依賴方向

```text
market_data
    ↓
realized_variance
    ↓
risk_forecast
    ↓
forecast_validation

apps/cli → composition only
```

consumer 只依賴 supplier 的 ports/DTO，不 import supplier 私有 adapters/application。
