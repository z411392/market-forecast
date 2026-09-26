# Requirements Specification

## Product

Market Forecast 是私人研究型風險預測系統。第一個產品輸出為 **future H=5 average realized variance / annualized volatility**。

## Semantic invariants

- B50 Current-State Momentum 不屬於本 repo 的 forecast target，也不重新最佳化。
- Risk Forecast 不輸出漲跌方向、Buy/Sell 或「bullish probability」。
- 模型/評分在 variance units；annualized volatility 僅 display transform。
- Primary horizon = 5 local trading sessions。
- H=20 = confirmatory only。
- Primary loss = QLIKE。

## Measurement governance

- canonical daily quantity = regular-session integrated variance proxy + overnight squared log return。
- 5m 是 practical reference，不是跨市場 ground truth。
- 5m/10m/15m 和 noise-robust reference 的 measurement audit 必須在任何 forecast-score-driven sampling selection 前完成。
- 原始 provider data 保留 provenance/hash；derived artifacts 可重建。

## Validation governance

- chronological expanding OOS。
- split unit = complete calendar date；跨市場 H/purge 依各 symbol local sessions。
- preprocessing/scaling train-only。
- final chronological holdout 不參與 tuning/model choice。
- pooled model 必須有 unseen-symbol transfer holdout。
- uncertainty 以 paired date-block bootstrap。
- market-specific promotion 必須在 unseen securities 與 final holdout 成立，且不能由單一標的驅動。

## Deployment

- offline research/fitting 可以 Python/uv。
- production inference 優先 freeze 成低維 manifest + Pine。
- Pine 不執行重新 fitting 或動態 model selection。
