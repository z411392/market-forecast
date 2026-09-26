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

## Task #10 S1 — canonical market-data contract design

Task #10 makes the `market_data` public contract concrete without selecting or calling a provider.
Provider-specific payload parsing remains in future driven adapters; public signatures contain owner DTOs only.

### Exact files and public symbols

| Path | Public symbol | Purpose |
|---|---|---|
| `src/libs/market_data/dtos/security_identity.py` | `SecurityIdentity` | canonical symbol/exchange/timezone/calendar identity |
| `src/libs/market_data/dtos/minute_bars_query.py` | `MinuteBarsQuery` | 1-minute read request by local session-date range |
| `src/libs/market_data/dtos/source_provenance.py` | `SourceProvenance` | provider/dataset/source-symbol/retrieval/raw artifact identity |
| `src/libs/market_data/dtos/canonical_minute_bar.py` | `CanonicalMinuteBar` | one observed 60-second OHLCV bar |
| `src/libs/market_data/dtos/minute_bars_batch.py` | `MinuteBarsBatch` | homogeneous query + provenance + immutable bar tuple |
| `src/libs/market_data/dtos/corporate_actions_query.py` | `CorporateActionsQuery` | dated corporate-action read request |
| `src/libs/market_data/dtos/corporate_action_fact.py` | `CorporateActionFact` | separate dated split/symbol-change/dividend/other fact |
| `src/libs/market_data/ports/read_minute_bars_port.py` | `ReadMinuteBarsPort` | provider-neutral minute-bar outbound port |
| `src/libs/market_data/ports/read_corporate_actions_port.py` | `ReadCorporateActionsPort` | provider-neutral corporate-action outbound port |
| `src/libs/market_data/exceptions/invalid_market_data_contract_error.py` | `InvalidMarketDataContractError` | stable adapter/parser contract failure |

### DTO field contract

All seven DTO symbols below are `TypedDict` contracts; no dataclass/Pydantic/provider SDK type is used in the public boundary.

`SecurityIdentity` required keys:

- `symbol: str` — canonical research symbol.
- `exchange: str` — canonical exchange identity.
- `timezone: str` — IANA timezone used for local session semantics.
- `calendar_id: str` — exchange-calendar identity used by downstream coverage/session logic.

`MinuteBarsQuery` required keys:

- `security: SecurityIdentity`
- `start_session_date: date`
- `end_session_date: date`
- `session_scope: Literal["regular", "all_observed"]`

`SourceProvenance` required keys:

- `provider: str`
- `provider_dataset: str`
- `source_symbol: str`
- `requested_start_session_date: date`
- `requested_end_session_date: date`
- `retrieved_at_utc: datetime`
- `raw_artifact_id: str`
- `raw_content_sha256: str`

`CanonicalMinuteBar` required keys:

- `security: SecurityIdentity`
- `bar_start_utc: datetime`
- `session_date: date`
- `open: float`
- `high: float`
- `low: float`
- `close: float`
- `volume: float`
- `price_basis: Literal["as_printed", "split_adjusted"]`

`MinuteBarsBatch` required keys:

- `query: MinuteBarsQuery`
- `provenance: SourceProvenance`
- `bars: tuple[CanonicalMinuteBar, ...]`

A missing minute is represented only by absence from `bars`; no DTO field authorizes forward-fill or synthetic bars.

`CorporateActionsQuery` required keys:

- `security: SecurityIdentity`
- `start_date: date`
- `end_date: date`

`CorporateActionFact` required keys:

- `security: SecurityIdentity`
- `action_type: Literal["split", "symbol_change", "cash_dividend", "other"]`
- `effective_date: date`
- `provenance: SourceProvenance`

Optional action-specific keys use `NotRequired`: `ratio: float`, `previous_symbol: str`, `new_symbol: str`,
`cash_amount: float`, `currency: str`.

Corporate-action field semantics:

- `effective_date` is the instrument-local market date on which the action becomes effective.
- for `action_type == "split"`, `ratio` means post-action shares divided by pre-action shares; a 10-for-1 split is `10.0`.
- `cash_amount` is source-reported cash per share in `currency`; it does not authorize dividend/total-return price adjustment.
- `previous_symbol` and `new_symbol` carry symbol-change semantics only.
- `other` preserves a dated/provenanced fact but does not overload split/symbol/dividend-specific fields; a future
  action type requiring new mandatory semantics must extend the contract explicitly.

### Port and failure contract

`ReadMinuteBarsPort.__call__(query: MinuteBarsQuery) -> MinuteBarsBatch`.

`ReadCorporateActionsPort.__call__(query: CorporateActionsQuery) -> tuple[CorporateActionFact, ...]`.

Both are ABCs owned by `market_data`. Provider SDK objects, DataFrame, raw JSON and HTTP response types are forbidden
from the public closure.

Driven adapters are responsible for rejecting provider observations that cannot be represented by the frozen contract,
including ambiguous adjustment state or timestamp/session identity. They map such failures to
`InvalidMarketDataContractError`; the exception exposes stable machine `type = "invalid_market_data_contract"` and remains provider-neutral. Exception messages must not contain credentials, provider account identity or raw provider responses. Adapter-specific parser functions
and provider error mappings are not implemented by Task #10.

### S2 frozen contract-test oracle

Before any production contract file is added, contract tests will assert:

- exact TypedDict required/optional key sets;
- `price_basis` and action-type Literal alternatives;
- UTC/session/provenance fields remain present in public annotations;
- port ABC signatures reference owner DTOs only;
- minute bars and corporate actions stay separate;
- public annotations do not expose provider SDK/HTTP/DataFrame/raw JSON types or an ambiguous `adjusted: bool` field.



## Task #11 S1 — strict deterministic realized-variance core

Task #11 starts with a provider-neutral pure-domain slice stacked on the exact #10 contract candidate. Live provider/session
completeness remains a separate dependency-gated integration concern.

### Exact public files

| Path | Public symbol | Purpose |
|---|---|---|
| `src/libs/realized_variance/dtos/aggregated_intraday_bar.py` | `AggregatedIntradayBar` | deterministic N-minute OHLCV bucket |
| `src/libs/realized_variance/dtos/intraday_realized_measures.py` | `IntradayRealizedMeasures` | regular-session RV/RQ/semivariance result |
| `src/libs/realized_variance/dtos/daily_realized_measures.py` | `DailyRealizedMeasures` | regular + overnight + whole-day result |
| `src/libs/realized_variance/exceptions/invalid_realized_variance_input_error.py` | `InvalidRealizedVarianceInputError` | stable fail-closed input error |
| `src/libs/realized_variance/constants/realized_variance_algorithm_version.py` | `REALIZED_VARIANCE_ALGORITHM_VERSION` | deterministic core identity (`rv-core-v1`) |
| `src/libs/realized_variance/domain/services/aggregate_minute_bars.py` | `aggregate_minute_bars` | strict 1m→5m/10m/15m aggregation |
| `src/libs/realized_variance/domain/services/calculate_intraday_realized_measures.py` | `calculate_intraday_realized_measures` | interval-return RV/RQ/semivariance |
| `src/libs/realized_variance/domain/services/calculate_overnight_log_return.py` | `calculate_overnight_log_return` | previous regular close → current regular open |
| `src/libs/realized_variance/domain/services/calculate_daily_realized_measures.py` | `calculate_daily_realized_measures` | whole-day composition |

No `__init__.py`, provider adapter, DataFrame, network type or CLI surface is added.

### AggregatedIntradayBar

Required keys:

- `security: SecurityIdentity`
- `session_date: date`
- `bar_start_utc: datetime`
- `interval_minutes: Literal[5, 10, 15]`
- `open: float`
- `high: float`
- `low: float`
- `close: float`
- `volume: float`
- `price_basis: Literal["as_printed", "split_adjusted"]`
- `source_minute_count: int`
- `algorithm_version: str`

The strict kernel requires `source_minute_count == interval_minutes`. `algorithm_version` is fixed to `REALIZED_VARIANCE_ALGORITHM_VERSION = "rv-core-v1"` for this contract version.

### IntradayRealizedMeasures

Required keys:

- `security: SecurityIdentity`
- `session_date: date`
- `sampling_minutes: Literal[5, 10, 15]`
- `price_basis: Literal["as_printed", "split_adjusted"]`
- `observation_count: int`
- `realized_variance: float`
- `realized_quarticity: float`
- `positive_semivariance: float`
- `negative_semivariance: float`
- `algorithm_version: str`

### DailyRealizedMeasures

Required keys:

- `security: SecurityIdentity`
- `session_date: date`
- `sampling_minutes: Literal[5, 10, 15]`
- `price_basis: Literal["as_printed", "split_adjusted"]`
- `regular_session_variance: float`
- `overnight_log_return: float`
- `overnight_variance: float`
- `whole_day_variance: float`
- `regular_positive_semivariance: float`
- `regular_negative_semivariance: float`
- `whole_day_positive_semivariance: float`
- `whole_day_negative_semivariance: float`
- `realized_quarticity: float`
- `observation_count: int`
- `algorithm_version: str`

### Measurement-identity propagation invariant

The adjustment basis is part of measurement identity and must survive every downstream transform:

```text
CanonicalMinuteBar.price_basis
→ AggregatedIntradayBar.price_basis
→ IntradayRealizedMeasures.price_basis
→ DailyRealizedMeasures.price_basis

REALIZED_VARIANCE_ALGORITHM_VERSION
→ AggregatedIntradayBar.algorithm_version
→ IntradayRealizedMeasures.algorithm_version
→ DailyRealizedMeasures.algorithm_version
```

No downstream measurement/audit/target code may compare or combine values while silently dropping either identity field.

### Strict aggregation invariants

`aggregate_minute_bars(bars, interval_minutes, session_start_utc)`:

- supports only 5 / 10 / 15;
- requires a non-empty tuple of `CanonicalMinuteBar`;
- requires exactly one security, one local `session_date`, and one `price_basis`;
- requires aware zero-offset UTC `bar_start_utc` and `session_start_utc`;
- requires first minute timestamp exactly equal to `session_start_utc`;
- requires timestamps strictly ordered and exactly one minute apart;
- requires total minute count divisible by the selected interval;
- never forward-fills or synthesizes bars;
- returns contiguous full buckets only;
- OHLCV aggregation is first open / max high / min low / last close / summed volume.

Any violation raises `InvalidRealizedVarianceInputError` with stable
`type = "invalid_realized_variance_input"`.

Legitimate provider/session shapes that do not fit the strict kernel must be resolved by explicit #4/#12 policy after live
acceptance; the kernel is not weakened speculatively.

### Interval returns and realized measures

For aggregated bars `b_0 ... b_(M-1)`:

```text
r_0 = log(close_0 / open_0)
r_i = log(close_i / close_(i-1)), i >= 1

RV  = Σ r_i²
RQ  = (M / 3) × Σ r_i⁴
RS+ = Σ r_i² where r_i >= 0
RS- = Σ r_i² where r_i < 0
```

All prices used in log returns must be finite and strictly positive. Input bars must have one security/session/sampling interval
and remain strictly ordered. `RS+ + RS-` must equal `RV` within floating-point tolerance.

### Overnight and whole-day composition

`calculate_overnight_log_return(previous_regular_close, current_regular_open)`:

```text
r_ON = log(current_regular_open / previous_regular_close)
```

Both prices must be finite and strictly positive.

`calculate_daily_realized_measures(intraday, overnight_log_return)`:

```text
overnight_variance = r_ON²
whole_day_variance = intraday.realized_variance + overnight_variance
```

The overnight variance is added to whole-day positive semivariance when `r_ON >= 0`, otherwise to whole-day negative
semivariance. Realized quarticity remains the regular-session high-frequency measure; Task #11 does not invent a whole-day RQ.

### S2 frozen test oracles

Before production implementation, tests must cover:

Positive:
- deterministic 1m→5m aggregation with exact OHLCV;
- same canonical minutes produce deterministic 10m and 15m results;
- hand-computed two/three-interval RV/RQ/RS+/RS-;
- semivariance identity;
- hand-computed overnight and whole-day composition.

Negative:
- unsupported interval;
- empty input;
- non-UTC / naive timestamp;
- first-minute anchor mismatch;
- duplicate/out-of-order/gapped minute;
- mixed security/session/price basis;
- non-divisible final bucket;
- non-positive return price;
- mixed sampling/session input to realized-measures calculation.

Provider-specific missing-bar meaning, early-close/auction classification and live completeness are outside S1–S4.
