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


### Task #11 S5c — downstream price-basis contract correction

Status: RED ORACLE REFROZEN; PRODUCTION NOT YET UPDATED.

Downstream Task #12 found that `IntradayRealizedMeasures` and `DailyRealizedMeasures` dropped the explicit
`price_basis` already present in canonical/aggregated bars. That would make later 5m/10m/15m comparisons unable to prove
that all measurements use the same adjustment basis.

Correction frozen in tests/design before production changes:
- both realized-measure DTOs require `price_basis: Literal["as_printed", "split_adjusted"]`;
- intraday calculation must propagate the homogeneous aggregated-bar basis;
- daily composition must propagate that basis unchanged;
- no formula, sampling, RV/RQ/semivariance or overnight behavior changes.

This refreeze intentionally makes the current production candidate incomplete until the follow-up GREEN commit lands.

### Task #12 upstream reconciliation — algorithm identity

Upstream exact candidate: `93da5e2d9ac4ab899181832583b33d3fb77897b6`.

Reconciled before any Task #12 production implementation:
- `price_basis` remains preserved through aggregated → intraday → daily measurements;
- `REALIZED_VARIANCE_ALGORITHM_VERSION = "rv-core-v1"` is now present;
- aggregated, intraday and daily measurement DTOs all carry `algorithm_version`;
- aggregation stamps the current version;
- intraday/daily calculation fails closed on unsupported algorithm versions and preserves the current version.

Task #12-specific RED audit/target tests remain owned by #12 and are preserved unchanged by this reconciliation.
No audit statistic, future-target production function, sampling choice, provider call or empirical freeze is added here.

### Task #12 S1 — audit/target contract freeze

Status: COMPLETE AS DESIGN; NO PRODUCTION CODE YET.

Key findings:
- aggregate correlations alone are insufficient for the Story AC because they erase the dates driving disagreement;
  therefore the contract includes dated `MeasurementAuditRow` records plus an aggregate summary.
- future target construction cannot infer local-session continuity from adjacent rows; the builder requires explicit
  `expected_session_dates` and verifies exact alignment before constructing H=5/H=20 windows.
- measurement audit remains forecast-score blind: no QLIKE/model field exists in the DTO/function contract.
- no outlier threshold is frozen; dated log gaps are retained so empirical S6 can report outliers without a post-hoc
  arbitrary cutoff becoming part of the measurement definition.
- target version is `whole_day_variance_v1`; audit version is `rv_measurement_audit_v1`.
- S1 does not freeze 5m as canonical across markets and does not make a U.S./Taiwan empirical claim.

Next:
- S2 commits positive/negative tests before any Task #12 production implementation.


### Task #11 downstream correction reconciled into Task #12

Reconciled upstream candidate:
- `d1a458b639ec952eac1d716d1e3b452f63a8a3d4`

Reason:
- Task #12 discovered that #11 originally dropped `price_basis` after aggregation.
- #11 refroze the invariant and propagated it through intraday and daily realized-measure DTOs/calculators.
- Task #12 now consumes that exact corrected source/test contract before S2 audit tests begin.

This reconciliation does not add measurement-audit behavior, select a sampling frequency, or change RV/RQ/semivariance formulas.


### Task #12 S1 correction — preserve price basis through audit and target identity

Status: DESIGN CORRECTED BEFORE TEST FREEZE.

Downstream readback found that the initial Task #12 S1 DTO design would have dropped `price_basis` again even though
Task #11 now preserves it through daily realized measurements.

Corrected contract:
- `MeasurementAuditRow`, `MeasurementAuditSummary`, and `FutureVarianceTarget` all require explicit
  `price_basis: Literal["as_printed", "split_adjusted"]`;
- audit alignment rejects mixed basis across 5m / 10m / 15m and across the call;
- audit summary propagates the common basis unchanged;
- future-target construction accepts one basis per call and propagates it to every target;
- mixed basis is explicitly included in the negative S2 oracle.

No statistical formula, horizon definition, sampling choice, or provider behavior changed.
S2 remains intentionally unstarted until this corrected design is durable.


### Task #12 S1 correction — preserve sampling identity in future targets

Status: DESIGN CORRECTED BEFORE TEST FREEZE.

Fresh-read found that the target builder accepted one sampling interval per call but `FutureVarianceTarget` did not record it.
That would make 5m-, 10m-, and 15m-based targets indistinguishable after construction.

Corrected contract:
- `FutureVarianceTarget` requires `sampling_minutes: Literal[5, 10, 15]`;
- `build_future_variance_targets` propagates the single input sampling interval unchanged;
- mixed sampling remains a negative oracle;
- this change does not select or promote any sampling frequency.

S2 remains intentionally unstarted until this measurement-identity correction is durable.
