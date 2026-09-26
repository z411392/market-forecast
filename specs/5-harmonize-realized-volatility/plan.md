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

### Port and failure contract

`ReadMinuteBarsPort.__call__(query: MinuteBarsQuery) -> MinuteBarsBatch`.

`ReadCorporateActionsPort.__call__(query: CorporateActionsQuery) -> tuple[CorporateActionFact, ...]`.

Both are ABCs owned by `market_data`. Provider SDK objects, DataFrame, raw JSON and HTTP response types are forbidden
from the public closure.

Driven adapters are responsible for rejecting provider observations that cannot be represented by the frozen contract,
including ambiguous adjustment state or timestamp/session identity. They map such failures to
`InvalidMarketDataContractError`; the exception type is stable and provider-neutral. Adapter-specific parser functions
and provider error mappings are not implemented by Task #10.

### S2 frozen contract-test oracle

Before any production contract file is added, contract tests will assert:

- exact TypedDict required/optional key sets;
- `price_basis` and action-type Literal alternatives;
- UTC/session/provenance fields remain present in public annotations;
- port ABC signatures reference owner DTOs only;
- minute bars and corporate actions stay separate;
- public annotations do not expose provider SDK/HTTP/DataFrame/raw JSON types or an ambiguous `adjusted: bool` field.

