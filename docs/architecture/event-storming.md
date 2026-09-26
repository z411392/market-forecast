# Event Storming — Risk Forecast v1.5

## Ubiquitous Language

- Raw Observation：provider 回傳、不可變的原始市場資料。
- Canonical Minute Bar：統一時區/標的/session 語義後的 1m OHLCV。
- Measurement Candidate：5m/10m/15m 或 noise-robust variance estimator。
- Measurement Freeze：在看 forecast score 前凍結 canonical target。
- Forecast Origin：在 t 可用資料下產生預測的時間點。
- Matured Target：未來 H 個 local sessions 全部完成後才可評分的 realization。
- Model Freeze：規格、係數、feature semantics、freeze date 一起凍結。
- Promotion Gate：challenger 可否替代 baseline 的預註冊門檻。

## 核心事件流

```text
Provider data acquired
→ Raw observation retained
→ Canonical minute bars built
→ Session coverage audited
→ RV candidates constructed
→ Measurement compared without forecast scores
→ Canonical measurement frozen
→ Forecast study preregistered
→ Chronological folds generated
→ Models fitted on training only
→ OOS forecasts emitted
→ Targets matured
→ QLIKE losses recorded
→ Date-block uncertainty computed
→ Promotion/stop gate adjudicated
→ Winning specification frozen
→ Pine artifact rendered
→ Python/Pine parity verified
```

## 關鍵政策

- sampling frequency 不能依 forecast winner 選。
- H=5 primary；H=20 不能救 H=5 failure。
- 同一 calendar date 的 cross-section 不拆 train/test。
- Taiwan/U.S. market identity 只有在 measurement + scale 控制後才可測 incremental value。
- 看完單一 symbol 結果後不可再挑 symbol-specific winner。
