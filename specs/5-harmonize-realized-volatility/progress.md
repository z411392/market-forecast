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

### Task #10 — canonical minute-bar / corporate-action contracts

Status: IN PROGRESS on `codex/10-canonical-minute-bar-contracts`.

S1 design finding:
- #4 live provider acceptance remains blocked, but its S2/S3 provider-neutral design is sufficient for #10.
- Public contracts are owned by `market_data`; no app, provider adapter, network call or provider promotion is part of this Task.
- Exact DTO/port/error paths and fields are frozen in `plan.md` before contract tests and production symbols.
- Missing minutes remain absence of observation; corporate actions remain separate dated facts.
- Story target formula formatting was repaired; product semantics are unchanged.

Next: S2 adds frozen positive/negative contract tests before production contract implementation.


### Task #10 S2 — contract tests frozen before implementation

Status: COMPLETE.

Frozen contract-test revision:
- `e42bc922801d9fbe9c1b29c44549f4f74fdd4099`

The tests lock:
- exact TypedDict required/optional key sets;
- `session_scope` / `price_basis` / corporate-action Literals;
- owner DTO-only ABC port signatures;
- stable `InvalidMarketDataContractError.type`;
- absence of ambiguous public `adjusted` fields.

No provider adapter or network call is part of this test slice.

### Task #10 S3 — minimal provider-neutral public contract

Status: COMPLETE AS CANDIDATE.

Candidate revision:
- `9de353281ddf2c70e54e69f3b156dc399388e94d`

Implemented exactly:
- seven owner TypedDicts;
- two outbound ABC ports;
- one typed provider-neutral contract exception.

Explicitly not implemented:
- Massive / FinMind / Databento adapters;
- provider-specific parsers;
- session normalization logic;
- forward-fill/synthetic bars;
- CLI/composition;
- live data access.

The S2 assertions/oracles were not changed by S3. The test files did receive import-order/formatting changes after the RED commit, so byte identity is not claimed.

### Task #10 S4 — semantic correction and structural readback

Status: READY FOR INDEPENDENT REVIEW, NOT ACCEPTED.

Corporate-action semantics were clarified without changing the public type shape:
- `effective_date` = instrument-local market date when the action becomes effective;
- split `ratio` = post-action shares / pre-action shares; 10-for-1 = `10.0`;
- `cash_amount` = source-reported cash per share in `currency`, not authorization for total-return adjustment;
- symbol-change fields are not overloaded by `other`.

Structural readback after S3 found:
- zero `__init__.py`;
- one public symbol per new Python file;
- no relative or function-local imports;
- current contract-test blobs differ only because of the later import-order correction; assertion readback is unchanged from the original S2 oracle (minute-bar 33/33, corporate-action 15/15, ports 11/11).

Remaining gate:
- repository-executed contract / architecture gates are not available through the current GitHub-only execution surface;
- independent Reviewer runtime is still `UNBOUND`.

Therefore Task #10 remains `REVIEW_PENDING`; downstream work may stack on the exact candidate contract, but final integration must not treat it as accepted until the missing gates are satisfied.


### Task #11 — deterministic RV measurement core

Status: CANDIDATE / REVIEW_PENDING.

S1 design:
- strict provider-neutral measurement kernel was frozen before production code;
- accepted live provider is not required for pure deterministic algorithms, but remains required for provider/session completeness integration;
- aggregation is anchored by explicit UTC session start and fails closed on gaps, duplicates, mixed session/security/basis, or partial final buckets.

S2 frozen behavior tests:
- revision `97295bfd073135d3e3bcb2c74efa45117975c5cd`;
- exact DTO/error contract;
- positive/negative 1m→5/10/15m aggregation;
- hand-computed RV/RQ/RS+/RS-;
- overnight return and whole-day composition;
- invalid timestamp/gap/basis/session/price cases.

S3 implementation:
- `54de510261e410a9e1f5d87ea1124c118048ecf6` — aggregated intraday bar DTO;
- `a36511ab41b8cbf31fba1baf3bd403c4a80a2c5a` — remaining DTOs + stable input error;
- `c2c1cd5ff43c6333de22cc4bd60a3edae392f9c9` — strict minute aggregation;
- `cf9edfd9b846bfa5577a64f90be731236cc7e05d` — intraday RV/RQ/semivariance.

S4 implementation:
- `eff075e8e3828bedff5619ce411b3f707a67d627` — overnight log return;
- `661169d3a2a214ca5718f762293887a7f4874473` — daily whole-day composition.

S5 static type-safety corrections:
- `7fe4525b05efa252b8df746e1d5e64b8f8c3cf0a` — explicit Optional previous-close narrowing;
- `33dac2111e5a6bcbbc1f2f5200504c5b7fa9936c` — literal TypedDict field access during validation.

Frozen S2 test files remain byte-identical through S5.

What this candidate proves:
- deterministic measurement semantics are now encoded in provider-neutral source and frozen tests;
- no provider/network/credential logic is present;
- no forward-fill/synthetic-bar path exists.

What remains unproven:
- repository-executed `make test-fast` / `make test-contract` / `make ci-fast` in a real checkout;
- legitimate provider-specific missing-bar / auction / early-close behavior;
- live Massive/FinMind parity;
- independent Reviewer acceptance.

Therefore Task #11 is not Done and measurement is not frozen by this candidate.
