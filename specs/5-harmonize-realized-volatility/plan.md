# Story #5 Plan

1. Complete provider acceptance Spike #4.
2. Define canonical bar DTO and provider port.
3. Implement provider adapters behind the port.
4. Persist immutable raw provenance and deterministic canonical transforms.
5. Implement 1m→5m/10m/15m aggregation.
6. Implement overnight / regular-session / whole-day RV plus RQ/semivariance diagnostics.
7. Run measurement-only U.S./Taiwan audit.
8. Freeze canonical target in spec + manifest.
9. Hand off frozen target semantics to Story #6.

No forecast score may be used to change steps 1–8 after measurement results are viewed.


## Spike #4 S2 — provider boundary design

The provider boundary is frozen before any live/provider-specific implementation.

### Raw vs canonical

Provider downloads are immutable raw observations. The driven adapter must not silently transform one vendor into another vendor's conventions.

Canonical 1-minute bars use these semantics:

- one row = one observed 60-second bar from one instrument;
- bar timestamp = bar-start instant normalized to UTC;
- local session date is derived with the instrument/exchange timezone and calendar, not UTC date;
- OHLC/volume values retain the provider's as-printed basis at the raw/canonical boundary;
- source provider, source symbol, retrieval range and raw artifact/content identity remain traceable;
- adjustment state is explicit; an adapter may not silently return split-adjusted bars under the same contract as unadjusted bars;
- corporate-action normalization is a separate versioned transform owned outside the provider adapter.

### Missing bars

- A missing minute is missing evidence, not a zero-return bar.
- Do not forward-fill OHLC in the provider adapter.
- Do not synthesize bars merely to make a regular grid.
- Coverage audit compares observed bars with the exchange/session calendar and records gaps explicitly.
- Early closes, halts, auctions and non-trading days are not generic missing-data errors; they must be classified using calendar/session evidence.

### Sessions

Primary RV uses the regular trading session plus a separately retained overnight component.

- pre-market / after-hours observations are not included in primary regular-session RV;
- opening/closing auction treatment must be measured and documented per market/provider before the measurement freeze;
- local market calendar is authoritative for session-date and local-session purge semantics;
- cross-market folds split by calendar date, but H/purge maturity is counted in each instrument's local sessions.

### Corporate actions

The research store must preserve enough information to distinguish genuine returns from mechanical price discontinuities.

- raw minute bars remain immutable/as observed;
- splits, symbol changes and other adjustment events are stored as separate dated facts when the provider supplies them;
- the measurement transform must declare its price-continuity rule and version;
- REST adjusted bars, flat-file unadjusted bars, or different provider conventions may not be concatenated without an explicit normalization step and overlap audit.

### Narrow acceptance oracle

Before any 30+30 universe backfill, test only AAPL, NVDA and 2330 over a small set of predeclared dates including:
- at least one ordinary session;
- at least one shortened/special session where applicable;
- at least one date around a known corporate-action boundary for a U.S. symbol;
- one recent date overlapping the existing TradingView manual-export evidence.

Acceptance compares:
1. timestamp/timezone/session identity;
2. expected vs observed minute coverage;
3. OHLCV sanity and bar ordering;
4. deterministic 1m -> 5m / 10m / 15m aggregation;
5. provider adjustment convention;
6. corporate-action discontinuity handling;
7. overlap against TradingView only as secondary parity evidence.

No provider is promoted from documentation alone.

## Spike #4 S3 refinement — 最小 live acceptance 呼叫計畫

本段只把已預註冊的 live acceptance 收斂成取得 credential 後可直接執行的最小呼叫集合；不在此執行 provider call。

### Massive

使用 Stocks Custom Bars：

`GET /v2/aggs/ticker/{ticker}/range/1/minute/{from}/{to}`

固定 query：

- `sort=asc`
- `limit=50000`
- primary acceptance 使用 `adjusted=false`，保留 as-printed basis。
- 僅在 NVDA split-boundary 對照額外呼叫同一區間 `adjusted=true`；兩種 basis 不得串接成同一序列。

預註冊最小 requests：

1. AAPL：`2024-07-02` 至 `2024-07-03`，`adjusted=false`，涵蓋 ordinary + early-close session shape。
2. NVDA：`2024-06-07` 至 `2024-06-10`，`adjusted=false`，涵蓋 10-for-1 split boundary。
3. NVDA：同區間 `adjusted=true`，只驗證 provider adjustment convention。

Massive 官方語義指出：沒有 qualifying trades 的 interval 不產生 aggregate bar，因此缺分鐘仍是缺失觀測，不做 forward-fill。

### FinMind TaiwanStockKBar

REST：

`GET https://api.finmindtrade.com/api/v4/data`

Bearer token + params：

- `dataset=TaiwanStockKBar`
- `data_id=2330`
- `start_date=<YYYY-MM-DD>`

資料集是 sponsor-only，且單次 request 只提供一天。回傳時間是 local `date` + `minute`，
adapter 必須依 `SecurityIdentity.timezone` 組合本地時間後轉 UTC，不得把字串直接解讀為 UTC。

預註冊最小 requests：

1. 2330 一個 ordinary trading date。
2. 2330 一個與 TradingView manual export 完全相同的 recent date。

第二個日期目前標記為 `PENDING_TRADINGVIEW_EXPORT_DATE`；repo 尚無可回讀的 TradingView export artifact/date，
禁止自行猜日期。

FinMind quota 可在 provider call 前透過 user-info endpoint 查詢；正式 acceptance 不含 bulk backfill。

### S4 開始條件

S4 live acceptance 僅在以下條件同時成立後開始：

- Massive API key 可用，且明示允許上述 3 個 bounded requests。
- FinMind sponsor-capable token 可用，且明示允許上述 bounded one-day requests。
- TradingView manual export 的實際日期／artifact identity 可追溯。
- provider call／quota 消耗授權已寫入 #4。


