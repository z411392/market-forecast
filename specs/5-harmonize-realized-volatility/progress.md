# Story #5 Progress

## 2026-09-26

- Story created as GitHub Issue #5.
- Kaledoxa-derived governance bootstrap started under #2.
- Provider acceptance Spike #4 created.
- Current candidate sources:
  - U.S.: Massive minute aggregates; Databento as alternative.
  - Taiwan: FinMind TaiwanStockKBar feasibility first.
  - Yahoo/yfinance: secondary daily sanity check only.
  - TradingView: Pine deployment/manual overlap spot-check only.
- No provider has been promoted yet.
- No paid/quota-consuming bulk download has been executed.


### Spike #4 S1 — official-source capability matrix

Status: COMPLETE (read-only research; no provider API call, purchase or bulk download executed).

Provisional rulings:

- Yahoo/yfinance: rejected as canonical historical intraday source because its documented intraday window is limited to the most recent 60 days.
- TradingView: rejected as Python historical data API; retained for Pine deployment and manual chart-data parity evidence only.
- Massive: primary U.S. acceptance candidate. Current Stocks Developer offering covers 10 years and includes minute aggregates, reference data and corporate actions. REST aggregates are split-adjusted by default; stock flat files are unadjusted. The adapter contract must make adjustment convention explicit and must never mix those silently.
- Databento: U.S. fallback candidate pending narrower consolidated-history/cost acceptance.
- FinMind TaiwanStockKBar: primary Taiwan feasibility candidate. Individual-stock minute K-bar coverage begins in 2019; sponsor access is one day per request, while SponsorPro supports whole-market daily parquet. Provider documentation explicitly records at least one historical missing date, so completeness must be audited rather than inferred from HTTP success.
- TWSE Data E-Shop: official Taiwan reference/institutional fallback. Historical intraday products extend to 2006; the detailed intraday product is internal-use licensed and publicly priced at NT$10,000 per subscribed month, so it is not the first private-pilot source.

Next: S2 freezes provider-port semantics, timestamp/session identity, adjusted-vs-as-printed policy and acceptance oracles before any live provider call.


### Spike #4 S2 — provider boundary semantics

Status: COMPLETE.

Frozen before live data access:

- canonical bar timestamp is UTC bar-start plus explicit local session date;
- provider/raw adjustment convention is explicit;
- provider adapters do not forward-fill or synthesize missing minutes;
- regular-session and overnight components remain separate;
- raw/as-observed bars and dated corporate-action facts remain distinct;
- corporate-action normalization is a versioned downstream transform;
- REST adjusted data and flat-file/provider unadjusted data cannot be silently concatenated.

Commit: `ca00cef9a9c33130fa56c7c4a65a8cc6096de5ac`.

### Spike #4 S3 — narrow live acceptance plan

Status: READY AS A PLAN; LIVE EXECUTION BLOCKED BY PROVIDER ACCESS/AUTHORIZATION.

Predeclared pilot instruments:
- AAPL
- NVDA
- TWSE 2330

Required evidence classes:
- ordinary regular session;
- U.S. early-close session;
- U.S. corporate-action boundary (NVDA 2024-06-10 split is the initial candidate);
- recent date overlapping existing TradingView manual-export evidence.

The live step must not start until credentials/subscription access and quota/spend authorization are explicit. No bulk backfill is part of the acceptance run.
