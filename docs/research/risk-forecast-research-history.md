# Market Forecast 研究歷程與重要設計決議

> Status: `REFERENCE_HISTORY`
>
> As of: 2026-09-28
>
> 本文件是研究歷程、重要轉折與設計決議的長期閱讀入口，不是第二份產品 authority、roadmap、Story status 或 decision log。
> 現行規則仍以 `docs/delivery/requirements-specification.md`、Story specs、GitHub Issues、Context Map 與相應 architecture authority 為準。
> 若本文件與 current authority 衝突，以 current authority 為準並修正本文件。
>
> 目的：讓後續研究者不用重翻聊天紀錄、TradingView CSV、離線 audit 與 Deep Research 報告，就能理解「研究過什麼、哪些方向已停止、哪些假設仍開放、為什麼目前走到 cross-market realized-volatility measurement」。

## 1. 產品問題是怎麼被拆開的

最早的核心問題其實混著兩件不同的事：

1. 現在的 momentum state 是什麼？
2. 未來的 return / volatility 會怎樣？

研究後正式把它們拆成兩條產品線：

```text
Current-State Momentum
    └─ B50
       回答：現在 momentum 在做什麼？

Forecast
    ├─ Risk Forecast
    │  回答：未來 realized variance / volatility 可能多大？
    ├─ Return Forecast Research
    │  回答：未來 return / cross-sectional rank 是否有可預測性？
    └─ Event / Tail Research
       回答：特定事件或尾部風險下會發生什麼？
```

這個拆分是整個專案最重要的語意決議之一。B50 不再被改造成 future-return probability，也不拿未來報酬重新最佳化。

現行 authority：
- [Epic #1](https://github.com/z411392/market-forecast/issues/1)
- `docs/delivery/requirements-specification.md`

## 2. Current-State Momentum：B50 的形成與 freeze

### 2.1 最終 production 定義

B50 使用三個當前狀態來源：

```text
D = (DI+ - DI-) × (ADX / 100)
```

DMI / ADX 參數為 14 / 14。

```text
B = ((High - EMA13) + (Low - EMA13)) / ATR14
```

MACD-V：

```text
MACDV = ((EMA12 - EMA26) / ATR26) × 100
```

```text
M = MACDV - EMA9(MACDV)
```

三個來源都使用只縮放、不移動 native zero 的 causal EWMA-RMS normalization：

```text
q_t = (1 - alpha) q_(t-1) + alpha × x_t²
```

其中：

```text
alpha = 1 - 2^(-1/20)
```

當期值除以前一根 bar 的 RMS：

```text
z_t = x_t / sqrt(q_(t-1))
```

再壓縮：

```text
u_t = tanh(z_t)
```

最終：

```text
B50 = 100 × (0.25 × uD + 0.50 × uB + 0.25 × uM)
```

語意：

- `0`：directional neutral / current-state boundary。
- `±50`：描述性的 strong momentum zones。
- 不是機率。
- 不是 universal Buy / Sell threshold。
- production validation 主要鎖在 1D。

### 2.2 Phase 1–2：從 sign vote 走到連續 state score

早期做過 sign vote、max-abs scaling、EWMA-RMS equal / median 等比較。

主要發現：

- BBP 最能提供 responsiveness / coverage。
- MACD-V 比較安靜、selective。
- DI-Power 保留明確 directional structure。
- Trend Strength 與 CMF 有研究，但沒有進 production。
- 4H 與 1D 的最佳 mixture 不一致，顯示 timeframe dependence。
- 最終把 1D 的 `25/50/25` 當作 production current-state mixture，而不是假設存在跨 timeframe 的 universal weights。

### 2.3 Phase 3：交易規則只作 probing，不把 B50 變成 strategy

測過三種 Long Only decision rules：

- Zero Cross：`B50 > 0` 進，`B50 < 0` 出。
- Strong Zone：cross `+50` 進，cross `0` 出。
- State + Slope：`B50 > 0` 且 rising 才持有。

Zero Cross 在 GOOGL / NVDA / QQQ / TSM / 2330 的歷史 probe 中都得到大於 1 的 Profit Factor；Strong Zone 在部分標的更好，但 TSM 並不穩；State + Slope 交易次數大增、平均持有時間很短，沒有形成一致優勢。

這個階段的決議不是「B50 是 trading system」，而是：

> B50 的 `0` 有穩定 current-state boundary 意義；`±50` 可以作 descriptive strength zone，但不應硬編 universal trading threshold。

另外曾發現 TradingView strategy 的 `slippage` 單位是 ticks；對 split-adjusted NVDA / 2330 會產生不合理結果，因此後續相關 probes 將 slippage 設為 0，成本主要用 commission sensitivity 檢查。

### 2.4 Phase 4：threshold / cost / temporal robustness

測過 `+40 / +50 / +60` strong-zone thresholds。

跨標的 median Profit Factor 大致形成 plateau，而不是單一尖峰；但 TSM 持續顯示 strong-zone rule 並非 universal。

成本提高後，Zero Cross 與部分 strong-zone variants 仍可維持大於 1，但 temporal split 顯示 regime dependence 很強。

因此 B50 最終 freeze 為 state indicator：

```text
0      primary directional-state boundary
±50    descriptive strong zones
Buy/Sell universal threshold    不成立
Probability                     不成立
```

## 3. Phase 5A：第一次 Future Return Forecast，結果為負

B50 freeze 之後，Forecast branch 不再用交易 probe 代替預測驗證，而是直接問：

> D / B / M 或 B50 能不能預測未來報酬？

### 3.1 Target 與驗證契約

標的：

- GOOGL
- QQQ
- NVDA
- TSM
- 2330

Horizons：

- H=1
- H=5
- H=10
- H=20

Binary target：

```text
1[log(C_(t+H) / C_t) > 0]
```

Continuous target：

```text
log(C_(t+H) / C_t)
```

模型只使用低複雜度、可解釋 baseline：

- L2 Logistic
- Ridge
- Huber

驗證：

- chronological per-symbol splits
- final 20% untouched holdout
- H-bar purge
- expanding TimeSeriesSplit
- inner chronological tuning
- train-only scaling
- no random shuffle
- explicit train-base-rate / zero / train-mean baselines

### 3.2 主要結果

Development OOS median improvement 都是負值。

Logistic 的 baseline minus model LogLoss improvement：

| Horizon | Median improvement |
|---|---:|
| H1 | -0.000473 |
| H5 | -0.001988 |
| H10 | -0.004389 |
| H20 | -0.014140 |

每個 horizon 都是 0/5 symbols 改善。

Median AUC 約：

| Horizon | Median AUC |
|---|---:|
| H1 | 0.487 |
| H5 | 0.493 |
| H10 | 0.496 |
| H20 | 0.460 |

Ridge development OOS RMSE improvement：

| Horizon | Median improvement |
|---|---:|
| H1 | -0.000023 |
| H5 | -0.000235 |
| H10 | -0.000607 |
| H20 | -0.002024 |

Huber 同樣沒有穩定改善。

更重要的是，超參數幾乎總是被推向最強 regularization 端：

- Logistic `C=0.01`：96/100 folds。
- Ridge `alpha=100`：96/100 folds。
- Huber `alpha=0.1`：97/100 folds。

這比較像「模型正在把弱訊號縮回去」，而不是「需要更複雜 ML」。

Moving-block bootstrap 也沒有任何穩定 improvement interval 支持 Logistic / Ridge / Huber。

### 3.3 Stop decision

正式決議：

```text
D / BBP / MACD-V / B50
對 absolute future return
沒有形成穩定 OOS evidence。

→ 不用 calibration / boosting / RLS / regime search
  去 rescue 同一套資訊。
```

這不是證明「股票未來報酬永遠不能預測」，而是證明：

> 目前這組 current-state momentum information 不足以支撐穩定的 absolute-return forecast。

Historical evidence artifact：
- `phase5a_quantitative_audit.md`（早期對話產物，尚未 materialize 到本 repo）

## 4. Forecast architecture 重新定位：先做 Risk，而不是硬救 Return

Phase 5A 之後的 Deep Research 把 Forecast 問題重新排列：

1. 第一個 Forecast product 應該是 volatility / risk。
2. Primary horizon 先用 H=5。
3. H=20 只作 confirmatory。
4. Return research 若重啟，優先做 broad cross-sectional residual-return rank，而不是五檔各自預測漲跌。
5. Options / analyst / fundamentals 等要視為真正的新 information layer，而不是拿更多 price indicators 堆模型。

這也是專案從「能不能預測方向」轉成「能不能先可靠預測風險」的主要轉折。

## 5. Risk Forecast v1：daily variance proxy + GARCH

### 5.1 Target

Primary：

```text
Y_(t,5) = (1/5) × Σ[h=1..5] r_(t+h)²
```

Confirmatory：

```text
Y_(t,20) = (1/20) × Σ[h=1..20] r_(t+h)²
```

這裡的 `r^2` 是 close-to-close squared log return；研究後來認為它足以證明 volatility persistence，但太粗，不應作為最終 canonical RV target。

### 5.2 Baselines 與 challengers

Baselines：

- historical mean variance
- current RV5
- RV20
- EWMA (lambda=0.94)
- GARCH(1,1)

Challengers：

- HAR-like
- RidgeCore
- RidgeStruct
- RidgeB50

Primary metric：QLIKE。

### 5.3 結果

GARCH 對 historical mean 的結果穩定很多：

```text
Development H5     4/5 better
Development H20    5/5 better
Holdout H5         5/5 better
Holdout H20        5/5 better
```

更複雜的 HAR / Ridge variants 對 GARCH 沒有穩定 development advantage。

B50 作為 risk predictor 的 incremental value 也不穩：

```text
Dev H5   1/5 vs RidgeStruct
Dev H20  2/5
Holdout H5 3/5
Holdout H20 2/5
```

決議：

```text
Risk target                PROMISING / CONTINUE
Simple GARCH baseline      KEEP
Rich exogenous model       NOT YET VALIDATED
B50 incremental risk value NO STABLE EVIDENCE
```

Historical evidence artifact：
- `risk_forecast_v1_audit.md`（早期對話產物，尚未 materialize 到本 repo）

## 6. Risk Forecast v1 Pine production candidate

為了 prospective tracking，建立過一支 TradingView-only frozen GARCH candidate：

`Risk Forecast v1 - 5D Expected Volatility`

當時只支援：

- GOOGL
- QQQ
- NVDA
- TSM
- 2330

固定 1D。

輸出：

- 5D expected annualized volatility
- 5D one-sigma move
- 20D expected annualized volatility
- trailing 20D realized volatility

不輸出：

- direction
- probability
- Buy / Sell

GARCH recursion：

```text
h_(t+1) = omega + alpha × r_t² + beta × h_t
```

多日平均 variance：

```text
avg_h_H = h_long_run + (h_1 - h_long_run) × (1 - p^H) / (H × (1 - p))
```

其中：

```text
p = alpha + beta
```

```text
h_long_run = omega / (1 - p)
```

當時 frozen coefficients 只用來做 prospective production candidate；後續歷史比較若要回看過去，必須重新做 causal / pseudo-prospective fit，不能拿 2026 freeze coefficients 回灌歷史。

這個 anti-leakage 決議後來成為所有 TradingView research variants 的固定原則。

## 7. Risk Forecast v2A：VIX / VXN incremental-value test，結果為負

下一個問題是：

> market-implied volatility 是否能在 GARCH 之外提供個股 H=5 variance forecast 的 incremental value？

測試：

- A0：GARCH
- A1：GARCH + VIX
- A2：GARCH + VXN
- A3：GARCH + VIX + VXN + one-day changes

四個 U.S.-listed domains：

- GOOGL
- QQQ
- NVDA
- TSM

使用 pseudo-prospective GARCH fitting，避免把 full-sample frozen coefficients 回測過去。

Primary H=5 結果：

```text
GARCH + VIX      Dev better 0/4, final holdout 0/4
GARCH + VXN      Dev better 0/4, final holdout 0/4
Full IV set      Dev better 0/4, final holdout 0/4
```

多數 median (Delta QLIKE) 反而為負。

20D 的 GOOGL 有極小局部 improvement，但沒有 replication，bootstrap interval 也跨 0。

決議：

```text
VIX/VXN 本身不是「沒有 volatility information」；
但在這四個 individual-security domains 上，
沒有穩定增加 GARCH 的 H=5 OOS forecast quality。

→ 不 promotion
→ 不做 transformation rescue
→ 不因失敗就一路 specification mining
```

Own-stock IV / skew 被保留成另一個真正不同的 hypothesis，但暫時不執行。

## 8. TradingView-first v1.5：用 5m realized variance 做 HAR

使用者希望 production / research 能盡量留在 TradingView，因此建立：

`Risk Forecast v1.5-TV - HAR Realized Volatility`

### 8.1 Whole-day RV

```text
RV_WD(t) = r_ON(t)² + Σ_j r_5m(t,j)²
```

其中：

```text
r_ON(t) = log(Open_t / Close_(t-1))
```

Primary future target：

```text
Y_(t,5) = (1/5) × Σ[h=1..5] RV_WD(t+h)
```

### 8.2 Causal HAR

Features：

```text
D_t = log(RV_t)
```

```text
W_t = log((1/5) × Σ[k=0..4] RV_(t-k))
```

```text
M_t = log((1/22) × Σ[k=0..21] RV_(t-k))
```

Direct H=5 regression：

```text
log(Y_(t,5)) = beta0 + betaD × D_t + betaW × W_t + betaM × M_t
```

在 bar `t` 只新增 origin `t-5` 的成熟 training label，因此不偷看未來。

## 9. Phase 2：HAR vs causal rolling GARCH

為了避免只拿 HAR 打弱 baseline，又加回 causal rolling GARCH。

GARCH 研究版：

- trailing 504 daily returns
- every 20 bars refit
- fixed (alpha × persistence) grid
- Gaussian QMLE
- H=5 average variance forecast

所有模型都對同一個 matured future-5D RV target 做 QLIKE。

### 9.1 五檔 pilot 結果

最近約 250 個成熟 forecasts 的 representative QLIKE：

| Symbol | HAR | GARCH | EWMA | Naive | HAR - GARCH |
|---|---:|---:|---:|---:|---:|
| GOOGL | 0.2508 | 0.2506 | 0.2575 | 0.3253 | +0.0002 |
| NVDA | 0.1052 | 0.1347 | 0.1136 | 0.1793 | -0.0295 |
| QQQ | 0.1757 | 0.1563 | 0.1877 | 0.2651 | +0.0195 |
| TSM | 0.1423 | 0.1222 | 0.1415 | 0.2236 | +0.0201 |
| 2330 | 0.1251 | 0.1959 | 0.1274 | 0.1630 | -0.0708 |

解讀：

```text
GOOGL   HAR ≈ GARCH
NVDA    HAR 較好
QQQ     GARCH 較好
TSM     GARCH 較好
2330    HAR 較好
```

四個美國 domains 在完全相同日期 equal-weight：

```text
HAR      0.16850
GARCH    0.16595
EWMA     0.17510
Naive    0.24832
```

HAR - GARCH 的 20-day block bootstrap interval 跨 0。

因此重要決議不是「不同股票挑不同贏家」，而是：

> HAR 與 GARCH 都顯示 volatility 可預測性，但沒有證據支持看完每檔結果後替每個 ticker 選自己的 winner。

事後做：

```text
NVDA -> HAR
QQQ  -> GARCH
TSM  -> GARCH
2330 -> HAR
```

會是 model-selection overfitting，除非有預先定義的 model-selection rule 並在 untouched future / transfer holdout 驗證。

## 10. Phase 3：5m / 10m / 15m RV measurement audit

HAR / GARCH 互有勝負之後，研究問題轉向更基礎的：

> 我們量 volatility 的尺本身穩不穩？

Primary 仍預註冊 5m；10m / 15m 只做 measurement sensitivity，不用哪一個讓 forecast QLIKE 最好來挑 sampling frequency。

### 10.1 GOOGL

最近 252 天：

| Comparison | Daily log-RV corr | 5D average RV corr |
|---|---:|---:|
| 5m vs 10m | 0.9587 | 0.9870 |
| 5m vs 15m | 0.9367 | 0.9811 |

在完整 5m coverage 區間，5D rank correlation 也約在 0.98 左右。

這支持：

> 單日 sampling-grid noise 存在，但 aggregation 到真正關心的 5D target 後，measurement story 非常一致。

### 10.2 U.S.-listed domains

GOOGL / QQQ / NVDA / TSM 的 5m / 10m / 15m 5D aggregate 高度一致，level bias 小。

因此 U.S. pilot 對 5m whole-day RV 的結論是：

```text
5m practical reference     可繼續
10m / 15m sensitivity      高度一致
用 forecast score 換 frequency 不允許
```

### 10.3 TWSE 2330

2330 顯示完全不同的 volatility signature：

```text
RV_5m > RV_10m > RV_15m
```

最近 252 個 5D windows 的觀測約為：

```text
5m > 10m    96.4%
10m > 15m   86.5%
5m > 10m > 15m 82.9%
```

level bias 約：

```text
5m vs 10m   +19.1%
5m vs 15m   +30.0%
```

同時 intrabar counts 穩定，因此不能簡單解釋成漏抓 K 棒。

這個結果只支持：

> 2330 的 fine-sampling measurement 對 microstructure / sampling grid 更敏感。

它不支持：

> 整個台灣市場一定需要不同 HAR / GARCH parameters。

這個 distinction 後來直接觸發 cross-market Deep Research。

## 11. HARQ 與更進階模型：為什麼先沒有直接往下衝

模型文獻研究後，最自然的下一個 challenger 是 HARQ，因為它不是隨便加 indicator，而是直接處理 realized-variance measurement error。

核心概念：

```text
RQ_t = (M / 3) × Σ_i r_(t,i)^4
```

HARQ 讓 daily RV coefficient 隨 quarticity / measurement noise 改變。

同時也研究了：

- HAR-RSV / leverage HAR
- Realized GARCH
- HEAVY
- Realized EGARCH
- shallow nonlinear ML
- HARNet / LSTM 類模型

但目前決議不是「越複雜越好」。

優先順序被收斂成：

```text
measurement quality
    ↓
HAR / GARCH / HARQ or asymmetry
    ↓
only if residual evidence remains
    ↓
more complex realized-volatility model
    ↓
deep / high-dimensional ML only with genuinely richer data
```

HARQ 本來要作 Phase 4A，但 2330 的 measurement signature 讓研究順序再次改變：

> 在 Taiwan measurement 還沒 harmonize 前，比較 U.S. / Taiwan HARQ coefficients 可能把 measurement-error difference 誤當成 market-dynamics difference。

## 12. Cross-Market Deep Research：Shared vs Market-Specific Parameters

新問題：

> 不同市場是否真的需要不同 volatility measurement 或 model parameters？

候選結構：

```text
A. Global shared model
B. Market-specific model
C. Symbol-specific model
D. Partial pooling / hierarchical shrinkage
E. Measurement issue first
```

Deep Research 的結論：

```text
Program direction: Path A
    先升級 intraday RV 並擴 universe

Cross-market gate: Path E first
    先解決 / harmonize measurement
    再正式測 A / B / D

目前沒有證據直接 promotion B / C / D
```

一個乾淨的 partial-pooling formulation：

```text
beta_i = beta_global + delta_market(i)
```

市場 deviation 要 shrink toward global，而不是直接替每個 ticker fit 一套完全獨立模型。

Market-specific model 若要 promotion，至少應滿足：

- unseen securities in same market 仍改善
- 多個 chronological OOS windows 同方向
- date-block bootstrap 支持
- final holdout 保留改善
- scale normalization 後仍成立
- 不由 2330 / NVDA 等單一標的驅動
- H=20 不嚴重相反
- 預註冊約至少 1% median H=5 QLIKE reduction，作為本專案 gate，不宣稱是 universal academic threshold

## 13. 為什麼研究 fitting 最後接受 Python，但 production 仍回 Pine

使用者最初希望整套都能在 TradingView 完成。

Pine 確實能：

- 取得目前 chart symbol 的 lower-timeframe intrabars
- 算 5m RV
- fit 小型 per-symbol HAR
- 跑固定 GARCH recursion
- 顯示 forecast

但實際研究碰到 TradingView lower-timeframe history / intrabar limits，而且跨市場正式研究需要：

- 30+30 symbols
- multi-year 1m data
- point-in-time universe
- consistent session / corporate-action handling
- complete-date cross-sectional splits
- symbol-transfer holdout
- nested tuning
- date-block bootstrap
- global / market-specific / shrinkage comparison

所以最終設計分工是：

```text
Python / uv
────────────────────────
multi-symbol intraday research
measurement harmonization
walk-forward fitting
global / market comparison
uncertainty / holdout
freeze model manifest

TradingView / Pine
────────────────────────
recent causal feature calculation
frozen coefficients / recursion
deterministic inference
5D expected volatility display
prospective tracking
```

這不是放棄 TradingView；而是把 TradingView 定位成 production inference，而不是 bulk research database。

## 14. Data-source design decisions

### 14.1 Yahoo / yfinance

Decision：

```text
daily sanity check       可用
2019–2026 intraday authority   不可用
```

原因：intraday history window 不足以支撐多年研究。

### 14.2 TradingView

Decision：

```text
Pine production / parity check     保留
Python automated historical source 不採用
scraping route                     不採用
```

TradingView manual `Export chart data` 可用作小範圍 overlap / parity evidence，但不當 canonical data API。

### 14.3 U.S.

Primary acceptance candidate：Massive。

設計注意：

- REST aggregate 與 flat-file adjustment semantics 可能不同。
- provider adapter 必須保留 source / adjustment identity。
- 不得把 adjusted / unadjusted series 靜默拼接。

Databento 保留成 U.S. fallback candidate。

### 14.4 Taiwan

Primary feasibility candidate：FinMind `TaiwanStockKBar`。

TWSE Data E-Shop 保留成官方 reference / institutional fallback，因成本與 licensing 較重，不作 private pilot 第一選擇。

現行 source work：
- [Spike #4](https://github.com/z411392/market-forecast/issues/4)

## 15. Canonical market-data boundary 已做出的設計決議

在任何 live provider implementation 前先 freeze：

### 15.1 Raw / canonical separation

Provider observation 是 immutable raw evidence。

Canonical 1m bar：

- timestamp 使用 UTC bar-start instant
- 另保留 instrument local session date
- source provider / source symbol 可追溯
- adjustment state explicit
- retrieval range / artifact identity / content hash 可追溯

### 15.2 Missing bars

- missing minute 就是 missing evidence
- adapter 不 forward-fill
- adapter 不為了規則網格合成 bar
- early close / halt / auction / non-trading day 必須用 calendar/session evidence 分類

### 15.3 Corporate actions

- raw bars 保持 as observed
- split / symbol change 等作 dated facts
- continuity normalization 是 downstream versioned transform
- adjustment convention 不藏在 adapter 裡

### 15.4 Session / overnight

Headline variance：

```text
V_WD(t) = V_RS(t) + r_ON(t)²
```

regular session 與 overnight component 在 research table 保持可分解。

不同市場不先假設相同 opening / closing auction effect。

## 16. Validation governance

專案逐步收斂出的 leakage / overfitting 防線：

### 16.1 Time

- chronological only
- no random shuffle
- complete-date split
- H-local-session purge
- final time holdout untouched

### 16.2 Cross-section

若做 pooled model：

- 同一 calendar date 的不同股票不能被拆去 train / test 兩邊
- 必須保留 unseen-symbol transfer holdout
- market-specific model 必須在沒參與 model selection 的同市場股票上成立

### 16.3 Preprocessing

- training-only fit
- scale normalization 與 dynamics 分開
- 不用 future statistics

### 16.4 Metric

Risk Forecast primary：

```text
QLIKE
```

secondary 才報：

- variance / log-variance RMSE
- MAE
- rank / calibration diagnostics

不能看完結果後換 primary metric。

### 16.5 Uncertainty

優先 paired block bootstrap over dates，保留時間與 cross-sectional dependence。

## 17. 明確停止或禁止 resurrect 的研究分支

### 17.1 B50 / D-B-M absolute-return rescue

除非加入真正新的 information set 或改成不同 problem geometry，否則不再：

- 換更複雜 classifier
- 做 calibration rescue
- 做 regime mining
- 無限 feature transform search

### 17.2 VIX / VXN rescue

v2A 已回答「index IV 是否穩定增加 individual-security GARCH H=5 quality」。

結果是否定的。

所以不再：

- 任意 VIX/VXN transformations
- 一直試到某一個 specification 好看

### 17.3 看 ticker 挑模型

不能因 pilot 結果：

```text
NVDA HAR 好
QQQ GARCH 好
2330 HAR 好
```

就建立 ticker-specific production switch。

需要 predeclared selector + untouched validation 才能成立。

### 17.4 直接把 2330 當 Taiwan

2330 只是一個 Taiwan pilot domain。

任何 `Taiwan-specific parameters` promotion 必須有更大的 TWSE panel 與 unseen securities。

## 18. 目前正式研究方向

現行研究主線：

```text
P0 Governance / architecture
        ↓
P1 U.S. / Taiwan intraday source acceptance
        ↓
P2 Measurement harmonization
   1m raw
     → 5m / 10m / 15m
     → overnight + regular session
     → noise / microstructure audit
     → canonical target freeze
        ↓
P3 Cross-market transferability
   global
   vs market-specific
   vs partial pooling
   + per-symbol GARCH/HAR baselines
   + unseen-symbol holdout
        ↓
P4 Freeze low-dimensional winner
        ↓
TradingView / Pine inference
        ↓
prospective post-freeze validation
```

現行 roadmap：
- `docs/delivery/mvp-phases.md`

現行 measurement Story：
- [Story #5](https://github.com/z411392/market-forecast/issues/5)

Cross-market Story：
- [Story #6](https://github.com/z411392/market-forecast/issues/6)

Pine deployment Story：
- [Story #7](https://github.com/z411392/market-forecast/issues/7)

## 19. 重要決議摘要

本節只是導航摘要；正式 authority 仍在 requirements / specs / Issues。

| 主題 | 已採決議 | 不代表 |
|---|---|---|
| B50 | frozen current-state momentum | future-return probability |
| B50 0 | primary state boundary | universal trading rule |
| B50 ±50 | descriptive strong zone | universal Buy/Sell |
| Absolute return Phase 5A | stop on current D/B/M/B50 information | markets are impossible to forecast |
| First Forecast product | Risk / volatility | one bullishness score |
| Risk primary horizon | H=5 | H=20 可救失敗 H=5 |
| Risk primary metric | QLIKE | 可事後換 metric |
| v1 baseline | GARCH retained | GARCH 已證明 universal best |
| VIX/VXN v2A | no stable incremental H=5 value | VIX has no information |
| HAR vs GARCH pilot | no stable universal winner | per-ticker switching is valid |
| U.S. 5m RV | practical reference passed pilot audit | 5m is universal ground truth |
| 2330 5m/10m/15m | measurement caveat | Taiwan definitely needs new parameters |
| Cross-market order | measurement first, then global vs market/shrinkage | coefficient plots alone justify market model |
| Research runtime | Python/uv acceptable | production must leave TradingView |
| Deployment | frozen low-dimensional Pine inference | Pine should refit panel models |
| Yahoo | secondary/daily only | multi-year intraday authority |
| TradingView data | manual parity + Pine | Python historical API |
| Raw bars | immutable / source-aware | silently normalized provider mix |
| Missing minute | missing evidence | zero-return / forward-filled bar |

## 20. Open hypotheses

以下仍然是研究問題，不是已知答案。

### 20.1 Market identity

```text
Does market identity add stable incremental forecast information?
```

在 measurement / scale 控制後，是否真的提供 stable incremental volatility dynamics？

要比較：

- global model
- market-specific model
- partial pooling

### 20.2 Taiwan measurement

2330 的 fine-sampling inflation 到底主要來自：

- microstructure noise
- intraday periodicity
- session / auction structure
- provider/data convention
- 其他 market-specific measurement effect

尚未證明是哪一個。

### 20.3 HARQ

在 target measurement freeze 後，HARQ 是否能穩定勝 matched HAR / GARCH？

尚未有 cross-market confirmatory evidence。

### 20.4 Own-stock options

Own-stock ATM IV / term structure / skew 可能是與 VIX/VXN 不同的 forward-looking information。

但它目前仍是 later registered hypothesis，沒有通過 sequence / data-cost gate。

### 20.5 Return forecasting

若未來重啟，優先研究 broad cross-sectional residual-return rank，而不是回到五檔 per-series direction。

需要 point-in-time broad panel，且多重測試治理要比一般研究更嚴。

## 21. Evidence map

### 21.1 Historical quantitative artifacts

下列檔案曾在研究對話中生成，但目前尚未 materialize 成本 repo current authority：

- `phase5a_quantitative_audit.md`
- `risk_forecast_v1_audit.md`
- Phase 5A dev / holdout / bootstrap CSVs
- Risk Forecast v1 dev / holdout / fold / bootstrap CSVs
- TradingView Phase 1–4 research exports
- Risk Forecast v1 / v1.5-TV / measurement-audit chart-data exports

它們屬 historical quantitative evidence，不應因未入 repo 就被當成不存在，也不應在未做 provenance/materialization 前冒充 repo-owned canonical artifact。

### 21.2 Deep Research

主要方法論研究曾依序涵蓋：

1. Current-State Composite vs Forecast separation。
2. Forecast Information Architecture。
3. Risk Forecast v1.5 target upgrade / larger-universe / options gate。
4. Cross-Market Volatility Forecasting — Shared vs Market-Specific Parameters。

最後一輪 cross-market research 的主結論：

```text
先 measurement Path E
再正式測 global / market-specific / partial pooling
```

### 21.3 Current GitHub navigation

- [Epic #1 — Risk Forecast v1.5](https://github.com/z411392/market-forecast/issues/1)
- [Story #5 — Measurement harmonization](https://github.com/z411392/market-forecast/issues/5)
- [Story #6 — Cross-market transferability](https://github.com/z411392/market-forecast/issues/6)
- [Story #7 — Pine deployment](https://github.com/z411392/market-forecast/issues/7)
- [Story #8 — Governed research workspace](https://github.com/z411392/market-forecast/issues/8)
- [Spike #4 — Intraday source acceptance](https://github.com/z411392/market-forecast/issues/4)
- [Task #10 — Canonical market-data contracts](https://github.com/z411392/market-forecast/issues/10)
- [Task #11 — Deterministic RV measurement](https://github.com/z411392/market-forecast/issues/11)
- [Task #12 — Measurement audit / freeze](https://github.com/z411392/market-forecast/issues/12)
- [Task #13 — Cross-market transferability study](https://github.com/z411392/market-forecast/issues/13)
- [Task #14 — Frozen manifest / Pine parity](https://github.com/z411392/market-forecast/issues/14)

## 22. 不要誤讀本文件

本文件不代表：

- 所有 historical experiment 都已在新 repo 可重播。
- Massive / FinMind 已通過 live acceptance。
- 30 U.S. + 30 TWSE panel 已建立。
- broad 30+30 global / market-specific / partial-pooling confirmatory program 已跑完；7-symbol pilot 已完成，但不等於 broad confirmatory panel。
- HARQ 已被 promotion。
- GARCH 已是永久最終模型。
- Taiwan 已被證明需要不同參數。
- Return forecasting 永久關閉。

它代表的是：

> 專案目前已經知道哪些問題被回答、哪些路被排除、哪些 uncertainty 還存在，以及下一個實驗應該如何避免重複犯同樣的 leakage / specification-mining 錯誤。


## 23. 2026-09-27 current-main update：7-symbol transfer pilot、Frozen v1 與 Story #6 現況

本節是 2026-09-26 歷史本文之後的 current-main 補充。它不改寫前面各階段當時的判斷；若前文的「open hypothesis」已被後續 pilot 部分回答，以本節較新的證據為準。

### 23.1 Supplied cross-market panel

後續實驗使用使用者提供的 TradingView Phase 4A exports：

- U.S.-listed：GOOGL / NVDA / QQQ / TSM
- Taiwan-listed：2330 / 2317 / 2454

這是 4 U.S. + 3 Taiwan 的 pilot panel，不是原 Deep Research 構想中的 30+30 broad universe。

原始 export SHA-256 已由 Tasks #25 / #27 / #29 / #31 的 replay runners 固定；後續 TradingView 新 export 不可冒充同一次 historical replay。

### 23.2 Level-HAR vs Log-HAR：早期 specification ambiguity 已測試

早期 v1.5 history 描述的是 Log-HAR；後來 Phase 4A / Frozen v1 實際使用 Level-HAR。

Task #23 做 matched H=5 comparison：

```text
overall Level-HAR QLIKE = 0.151967
overall Log-HAR QLIKE   = 0.151992
Log - Level             = +0.000025
95% block-bootstrap CI  = [-0.018214, +0.029104]
```

U.S. / Taiwan point estimates方向相反；NVDA 較偏 Log-HAR，2454 較偏 Level-HAR，其餘多數 symbol CI 跨 0。

決議：

```text
Frozen v1 Level-HAR            KEEP
Switch production to Log-HAR   NO
Ticker-specific transform rule NO
```

這不代表 Level-HAR universal superior；只代表 supplied pilot 沒有 evidence 支持為了早期 Log-HAR 設計而改掉 Frozen v1。

Current-main artifacts：

- `docs/research/experiments/run_task_23_level_vs_log_har.py`
- `docs/research/experiments/task-23-level-vs-log-har.{md,csv}`

### 23.3 Global vs market-specific Ridge-HAR：current reproducible reference

Task #25 修復 Task #13 S2 的 replayability gap。舊 S2 table 保留為 historical evidence，但因當時沒有 exact committed market-specific runner，current replay reference 以 Task #25 為準。

H=5 unseen-symbol date-equal-weight：

```text
market-specific - global

Overall  +0.0019338184
95% CI   [+0.0010117372, +0.0032456959]

U.S.     +0.0019304047
95% CI   [+0.0007582508, +0.0034437085]

Taiwan   +0.0021311598
95% CI   [-0.0010763065, +0.0055983506]
```

Positive delta 表示 global QLIKE 較低。

決議：

- market-specific Ridge-HAR 不 promotion；
- U.S. unseen-symbol transfer 在 final window 偏 global；
- Taiwan 仍 inconclusive；
- 不建立 Taiwan-specific parameter set。

Current-main artifacts：

- `docs/research/experiments/run_task_25_ridge_har_reproducibility.py`
- `docs/research/experiments/task-25-ridge-har-reproducibility.{md,csv}`

### 23.4 Fixed-alpha partial pooling：沒有形成有用的中間解

Task #27 使用預註冊 market coding：

```text
U.S.    m = -0.5
Taiwan  m = +0.5
```

Pooled design：

```text
xD, xW, m, m*xD, m*xW
```

固定 Ridge `alpha=1.0`，不看 test tuning。

結果：

```text
overall partial - global = +0.00193414
95% CI = [+0.00101289, +0.00324652]

overall partial - market = +3.21e-7
95% CI = [-1.78e-6, +2.55e-6]
```

這個 candidate 幾乎與 market-specific fit 重合，沒有形成實質 intermediate pooling benefit。

決議：

- fixed-alpha market-deviation partial pooling 不 promotion；
- 不在同一 Task 看完結果後 tuning alpha rescue；
- 不改 production Frozen v1。

Current-main artifacts：

- `docs/research/experiments/run_task_27_partial_pooling.py`
- `docs/research/experiments/task-27-partial-pooling.{md,csv}`

### 23.5 H=20 confirmatory：沒有推翻 H=5

Task #29 將 target 改為 future 20 local sessions，且每個 training origin 的第 20 個 target session 必須嚴格早於 evaluation start，避免用 calendar-day approximation 代替 purge。

結果：

```text
overall market - global = +0.00231986
95% CI = [+0.00028179, +0.00354572]

overall partial - global = +0.00232077
95% CI = [+0.00028344, +0.00354674]
```

U.S. 也偏 global；Taiwan 仍 inconclusive。

決議：

```text
H=5 primary transfer ruling             NOT CONTRADICTED
Market-specific Ridge-HAR               NOT PROMOTED
Fixed-alpha market-deviation partial    NOT PROMOTED
```

Current-main artifacts：

- `docs/research/experiments/run_task_29_h20_transfer.py`
- `docs/research/experiments/task-29-h20-transfer.{md,csv}`

### 23.6 Multiple-window expanding OOS：global 優勢有 temporal heterogeneity

Task #31 預註冊四個不重疊 H=5 evaluation windows，每個 fold 都重新 fitting，training label 必須在 fold start 前以各 symbol local-session target 完全成熟。

Overall `market-specific - global`：

| Fold | Window | Delta QLIKE | 95% CI | Interpretation |
|---|---|---:|---:|---|
| F1 | 2024-12-02 .. 2025-03-31 | +0.006985 | [-0.001228, +0.015575] | global point estimate，inconclusive |
| F2 | 2025-04-01 .. 2025-07-31 | -0.001405 | [-0.005018, +0.004961] | market point estimate，inconclusive |
| F3 | 2025-08-01 .. 2025-12-03 | +0.003247 | [+0.002411, +0.005746] | global better |
| F4 | 2025-12-04 .. data end | +0.001945 | [+0.001024, +0.003258] | global better |

因此：

- 不可再說「global 在每個 chronological window 都穩定勝」；
- later F3/F4 支持 global；
- early F1/F2 無法 cleanly separate；
- 沒有任何 fold 穩定支持 market-specific improvement；
- Taiwan 四個 folds 都 inconclusive；
- temporal transfer evidence 是 heterogeneous。

這個 finding 會弱化 global robustness 的語氣，但不改 market-specific NOT PROMOTED 的決議。

Current-main artifacts：

- `docs/research/experiments/run_task_31_expanding_oos.py`
- `docs/research/experiments/task-31-expanding-oos.{md,csv}`

### 23.7 Frozen v1 deployment 已落 main

Task #14 已完成：

- selected model class：Level-HAR；
- seven supported ticker IDs；
- Python snapshot/freeze 504 matured rows 的 per-symbol coefficients；
- manifest + golden fixtures；
- Pine deterministic inference only；
- unsupported ticker fail closed；
- `ticker.standard(syminfo.tickerid)` canonicalizes TradingView modifiers；
- freeze date 前 suppress frozen forecast，避免 2026 coefficients 回灌歷史；
- GOOGL corrected Frozen v1 TradingView runtime export 與 golden parity 通過。

Production artifact：

- `pine/risk_forecast_v1_5_tv_har_frozen_v1.pine`
- `artifacts/model-manifests/risk_forecast_har_frozen_v1.json`
- `artifacts/model-manifests/risk_forecast_har_frozen_v1_golden.csv`

這仍是 `PROSPECTIVE_FROZEN_PILOT`，不是 universal cross-market model claim。

### 23.8 Story #6 current-main acceptance matrix

| Requirement | Current-main status | Evidence |
|---|---|---|
| H=5 primary QLIKE | PROVEN | Tasks #25 / #27 / #31 |
| unseen-symbol transfer | PROVEN | Task #25 |
| global vs market-specific | PROVEN | Task #25 |
| ridge-shrunk market deviations | PROVEN | Task #27 |
| H=20 confirmatory | PROVEN | Task #29 |
| multiple expanding OOS windows | PROVEN | Task #31 |
| local-session purge / target maturity | PROVEN | Tasks #29 / #31 |
| paired date-block bootstrap | PROVEN | Tasks #23 / #25 / #27 / #29 / #31 |
| train-only scaling | PROVEN | replay runners |
| per-symbol HAR/GARCH mandatory baseline on final supplied panel | PROVEN | Task #35 |
| recent-variance / EWMA / naive comparator on final supplied panel | PROVEN | Task #35 |

因此截至 2026-09-27，Story #6 的 supplied 4+3 pilot model/validation evidence 已在 current main durable；不再有 comparator replay gap。

但 #13 / Story #6 仍不應 formal close，因兩者明確依賴 Story #5 canonical target freeze。Story #5 / Task #12 的 final empirical measurement freeze 仍被 #4 live provider acceptance 擋住。現在的 TradingView 5m whole-day RV 是 practical pilot reference，不應被重新命名成已完成的 canonical cross-market frozen target。

### 23.9 Market identity hypothesis 的最新狀態

原 Section 20.1 的問題：

```text
Does market identity add stable incremental forecast information?
```

在 supplied 4+3 pilot 上已部分回答：

- market-specific 沒有 stable unseen-symbol incremental value；
- fixed-alpha partial pooling 沒有改善；
- H=20 不推翻 H=5；
- chronological windows 顯示 transfer effect 有 temporal heterogeneity；
- Taiwan-specific parameters 沒有得到支持。

但 broad universe（例如原計畫 30+30）、完整 measurement harmonization 與真正 hierarchical shrinkage 仍未完成，因此不能把這個 pilot 上升成 universal market-identity theorem。


### 23.10 Final HAR / GARCH / EWMA / naive comparator 已 current-main replay

Task #35 將舊 Draft PR #21 的 final comparator 重新做成 hash-pinned、dependency-light、可執行的 current-main evidence。

Alignment oracle：

- 35 / 35 symbol × comparator 的 origin forecast / matured exported QLIKE 對齊檢查通過；
- worst max absolute difference = `1.7763568394002505e-15`；
- declared tolerance = `1e-12`。

Final-window overall paired date-block bootstrap：

```text
HAR - Global   = -0.013993
95% CI         = [-0.044484, +0.003130]

HAR - GARCH    = -0.022675
95% CI         = [-0.053313, -0.006911]

HARQ - HAR     = +0.000506
95% CI         = [-0.000383, +0.001776]

EWMA - HAR     = +0.012462
95% CI         = [+0.000081, +0.034094]

Naive - HAR    = +0.066828
95% CI         = [+0.037997, +0.111866]
```

決議：

- causal Pine Level-HAR 保留為 supplied-panel primary baseline；
- GARCH 保留 comparator，不作 primary；
- HARQ 不 promotion；
- EWMA 不勝 HAR overall；
- naive / recent-variance baseline 明確較弱；
- global Ridge-HAR 不足以取代 causal Pine HAR；
- 不建立 ticker-specific winner switch。

Current-main artifacts：

- `docs/research/experiments/run_task_35_final_comparator_replay.py`
- `docs/research/experiments/task-35-final-comparator-per-symbol.csv`
- `docs/research/experiments/task-35-final-comparator-bootstrap.csv`
- `docs/research/experiments/task-35-final-comparator-alignment.csv`
- `docs/research/experiments/task-35-final-comparator-replay.md`

### 23.11 Story #6 closure status：pilot evidence complete，formal closure dependency-blocked

截至 Task #35：

```text
Story #6 supplied-panel model matrix      COMPLETE
H=5 primary transfer evidence            COMPLETE
H=20 confirmatory evidence               COMPLETE
multiple-window expanding OOS            COMPLETE
per-symbol HAR/GARCH/EWMA/naive baseline COMPLETE
current-main replayability               COMPLETE

Story #5 canonical target freeze         NOT COMPLETE
Task #12 final empirical freeze          BLOCKED by #4 live provider acceptance
```

因此目前最精確的狀態是：

> Story #6 / Task #13 在 supplied 4+3 pilot 的 model-selection / validation evidence 上已完成，但 formal Story closure 仍受上游 Story #5 canonical measurement freeze 約束。

這不是模型證據不足，也不是要求再 specification mining。下一步若要解除 formal blocker，應回到 Story #5 / #4 / #12 的 data-source acceptance 與 empirical measurement freeze，而不是再增加 forecasting model。


## 24. 2026-09-28 TradingView deployment status reconciliation

Current-main readback confirms the production deployment path is no longer the old external-source bridge experiment.

### 24.1 Story #7 is implementation-complete

Story #7 declared one child Task:

- #14 — Freeze model manifest and verify Pine parity.

Task #14 is closed/completed, and current `main` contains the accepted deployment artifacts:

- `pine/risk_forecast_v1_5_tv_har_frozen_v1.pine`;
- `artifacts/model-manifests/risk_forecast_har_frozen_v1.json`;
- `artifacts/model-manifests/risk_forecast_har_frozen_v1_golden.csv`.

Current-main identities at reconciliation time:

- production Pine blob: `5fe0de0f55b1a0d44cc83278aaae068bdd9bdd6e`;
- model manifest blob: `261c6dcfaba545ced19cb28f1ad5d7fc4ab976f7`;
- golden fixture blob: `78e683e74b4bb368afb2cecfec938b64a3b7e0f4`.

The deployment AC are satisfied:

- coefficients/spec/freeze date/input semantics/version are traceable through the manifest;
- Python/golden parity exists and was executed;
- corrected GOOGL TradingView runtime/export parity passed;
- Pine performs deterministic inference only and does not refit;
- output semantics remain volatility/risk, not direction probability or Buy/Sell.

Story #7 can therefore be treated as completed even though Story #6 remains formally open on its upstream Story #5 measurement-freeze dependency. Story #7 required a promotion ruling, and the supplied-panel ruling used by Task #14 already exists; it did not require Story #6 itself to be closed.

### 24.2 Task #20 is superseded, not a production path

Task #20 created `pine/experiments/market_forecast_risk_bridge.pine` as an `EXPERIMENT_ONLY` fallback when the exact current Pine sources were unavailable.

Its own contract said the bridge was:

- external-source only;
- no model fitting;
- no coefficient changes;
- fully replaceable once exact source / frozen model artifacts were available.

That replacement condition is now satisfied by Task #14 Frozen v1.

Therefore Task #20 is retained only as historical integration evidence and should be closed as superseded / not planned. It must not be confused with the current production deployment path.

### 24.3 Current deployment authority

Current deployment authority is:

```text
Frozen v1 manifest
    +
deterministic HAR Frozen v1 Pine
    +
golden fixtures
    +
TradingView runtime parity evidence
```

The external-source bridge is not required for production operation or acceptance.
