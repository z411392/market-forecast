# Task #90 S1 — Taiwan Noise-Robust Benchmark Feasibility Freeze

Task: #90  
Parent measurement task: #12  
Source evidence: #89 accepted Taiwan v4 panel, #86 XTAI measurement semantics  
Status: S1 research/feasibility only — no estimator production code and no new provider call in this slice.

## Decision

Primary independent benchmark family:

`taiwan-rk-parzen-trade-v1`

Estimator:

- univariate non-negative realized kernel;
- Parzen kernel weights;
- transaction-price input from Shioaji historical `Ticks`;
- data-driven bandwidth;
- provider transaction order preserved.

Secondary sensitivity family:

- TSRV / MSRV only if the realized-kernel benchmark exposes a material implementation or data-quality instability.

Not selected as the primary benchmark:

- Bandi–Russell MSE-optimal classical-RV sampling.

The reason is methodological rather than numerical: an optimized classical-RV sampling interval still answers the question by choosing a sparse classical-RV frequency, while Task #90 requires an independent benchmark against which the 5m / 10m / 15m fixed-grid candidates can be evaluated.

No fixed-grid candidate has been promoted by this decision.

## Why realized kernel is the primary family

The unresolved Taiwan problem from Task #89 is not whether 5m / 10m / 15m track the same volatility state. They do.

The unresolved problem is measurement scale:

- panel-median Pearson log-RV 5m/10m = 0.96476;
- panel-median Pearson log-RV 5m/15m = 0.94274;
- panel-median geometric 5m-vs-10m bias = +14.75%;
- panel-median geometric 5m-vs-15m bias = +25.58%.

All three pilot symbols show positive 5m-vs-coarser level bias.

A realized kernel is suitable as the independent benchmark because it is designed for high-frequency noisy prices rather than for one selected sparse calendar grid.

The practical Barndorff-Nielsen / Hansen / Lunde / Shephard implementation:

- can be applied to trade data;
- uses a non-negative Parzen kernel;
- supports microstructure-noise robustness;
- is robust to serial dependence in the noise;
- provides a data-driven bandwidth rule.

Primary references:

- Barndorff-Nielsen, Hansen, Lunde & Shephard, *Realized Kernels in Practice: Trades and Quotes*  
  https://doi.org/10.1111/j.1368-423X.2008.00275.x
- Bandi & Russell, *Microstructure Noise, Realized Variance, and Optimal Sampling*  
  https://ideas.repec.org/a/oup/restud/v75y2008i2p339-369.html
- Aït-Sahalia / Mykland review of two-/multi-scale realized volatility  
  https://link.springer.com/chapter/10.1007/978-3-540-71297-8_25

## Source decision

### Realized-kernel input — Shioaji historical ticks

Primary benchmark input:

- `api.ticks(..., query_type=TicksQueryType.AllDay)`;
- one stock / one session per query;
- transaction price = tick `close`;
- provider row order is authoritative when timestamps are equal.

Official Shioaji historical-data documentation:

https://sinotrade.github.io/tutor/market_data/historical/

The benchmark must not use the accepted 1m Kbars as its primary high-frequency source.

Reason:

Using the same minute-aggregated evidence that produced the 5m / 10m / 15m candidates would reduce the independence of the benchmark.

### Kbar role

Historical Kbars remain valid for:

- reproducing the accepted Task #86 / #89 fixed-grid daily measurements;
- session/date coverage reconciliation;
- fixed-grid benchmark-comparison rows.

They are not the source for the primary realized-kernel estimator.

## Tick validation contract to freeze in S2

Before any realized-kernel calculation, one session of tick evidence must satisfy:

- security identity is fixed;
- requested session date is exact;
- timestamps are non-decreasing;
- provider ordering is preserved for equal timestamps;
- transaction prices are finite and strictly positive;
- no timestamp belongs to another session;
- no row is silently deleted solely because multiple trades share one timestamp.

No synthetic transaction may be inserted.

No previous-tick calendar fill is needed for the primary realized-kernel transaction sequence.

## XTAI session semantics

Intraday realized-kernel evidence uses the actual transaction sequence.

Opening:

- first matched trade is the official session opening price;
- no synthetic 09:00 transaction is created when the first trade occurs later.

Closing:

- the 13:30 closing-auction trade is included as the terminal intraday observation when present;
- missing closing-auction evidence fails closed.

No-trade intervals:

- transaction-time gaps are allowed;
- no calendar-time minute or boundary observation is synthesized for the realized-kernel benchmark.

This deliberately differs from Task #86 fixed-grid sampling, where previous-tick calendar-time prices are needed to define fixed sampling boundaries.

## Whole-day benchmark semantics

The primary benchmark remains a whole-day variance target.

Define:

`whole_day_variance_rk = intraday_realized_kernel + overnight_log_return^2`

Overnight return:

`log(current official first matched trade / previous validated 13:30 closing-auction price)`

The same overnight-return semantic is used by the accepted Task #86 / #89 measurement path.

The realized kernel only replaces the intraday fixed-grid realized-variance component.

## Frozen kernel family

Kernel:

Parzen.

For `0 <= x <= 1/2`:

`k(x) = 1 - 6x^2 + 6x^3`

For `1/2 < x <= 1`:

`k(x) = 2(1-x)^3`

For `x > 1`:

`k(x) = 0`

Estimator form:

`RK = gamma_0 + 2 * sum_{h=1..H} k(h/(H+1)) * gamma_h`

where `gamma_h` is the realized autocovariance of log transaction returns.

Exact indexing and finite-sample edge behavior are S2 test-owned details and must be frozen before production code.

## Bandwidth direction

Practical Parzen bandwidth:

`H_hat = 3.5134 * xi_hat^(4/5) * n^(3/5)`

with practical plug-in:

`xi_hat^2 = omega_hat^2 / IV_hat`

### Preliminary IV

Primary S2 design direction:

- sparse 20-minute calendar-time realized variance;
- previous-tick price at sparse calendar boundaries;
- average across deterministic time offsets.

The sparse preliminary IV exists only for bandwidth selection.

It is not the Task #90 benchmark output.

### Noise variance

Estimate `omega_hat^2` from offset subgrids.

Practical source rule from the realized-kernel implementation literature:

- choose `q` so every q-th transaction is approximately two minutes apart;
- compute q offset dense realized variances;
- for each offset:
  `omega_hat_i^2 = RV_dense_i / (2 * n_i)`;
- `n_i` counts non-zero returns used by that offset;
- average over the q estimates.

Exact deterministic q rounding and zero-return handling must be frozen in S2.

### Endpoint jittering

S1 direction:

`m = 1`

The practical literature reports that m=1 is commonly optimal and that small changes in m often have negligible empirical impact.

S2 must still freeze the exact endpoint-return construction and failure behavior before implementation.

## Estimator identity

Primary benchmark identity:

`taiwan-rk-parzen-trade-v1`

The identity must include, either directly or via a manifest hash:

- Parzen kernel;
- bandwidth-selector version;
- q-selection rule;
- endpoint-jitter rule;
- tick-cleaning/validation version;
- XTAI session semantic version;
- overnight composition version.

Changing any of these requires a new benchmark identity.

## Immutable evidence

For every historical tick query persisted for Task #90:

- provider = Shioaji;
- provider version;
- symbol;
- requested session date;
- normalized SDK tick payload SHA-256;
- row count;
- first and last transaction timestamps;
- validation result.

Do not commit credentials or account identity.

Provider SDK payload evidence should be immutable and independently hashable.

## Provider-traffic feasibility

Current Shioaji official limits for a stock account with no API trading amount:

- 500 MB historical/market-data traffic per day;
- traffic resets at 08:00 on a trading day;
- total market-data request rate up to 50 calls / 10 seconds;
- historical `ticks` / `kbars` are intended for after-market analysis/backtesting and should be cached.

Official usage limits:

https://sinotrade.github.io/tutor/limit/

Full existing Taiwan pilot evidence window:

- 3 symbols;
- 253 source sessions per symbol, including the prior session needed for the first overnight return;
- maximum tick-query count = `3 * 253 = 759`.

If fixed-grid daily rows must be recomputed in the same empirical run:

- approximately 42 bounded Kbar chunk calls are additionally required.

## Traffic execution rule for S3

Do not issue all 759 tick requests blindly.

S3 must:

1. run after market close;
2. keep one login/session;
3. query one session once and cache it;
4. inspect `api.usage()` before the first batch;
5. re-check usage after every bounded batch;
6. stop well before the daily traffic ceiling;
7. preserve completed batch artifacts so later runs can resume without re-querying.

Initial conservative traffic stop boundary:

- stop when total Task #90 traffic in the current run reaches 250 MB, or
- stop when provider-reported remaining daily traffic falls below 250 MB,

whichever occurs first.

This keeps the benchmark program materially away from the 500 MB no-trading daily cap.

The threshold may only be changed by a separate documented decision.

## Candidate comparison summary

| Candidate | Primary source | Independent of 5/10/15 grid | Noise robust | Main extra tuning | S1 status |
|---|---|---:|---:|---|---|
| Parzen realized kernel | historical trade ticks | yes | yes | kernel bandwidth | PRIMARY |
| TSRV / MSRV | ticks or dense calendar prices | yes | yes | subsample/multiscale design | secondary sensitivity |
| MSE-optimal classical RV | high-frequency prices | partially | chooses classical sampling | per-asset/time optimal grid | diagnostic only |

## S2 tests-first scope

S2 must freeze deterministic oracles for:

- Parzen weights;
- realized autocovariances;
- realized-kernel value on hand-checkable returns;
- non-negativity expectation within numerical tolerance;
- q selection;
- noise-variance subgrids;
- sparse 20-minute preliminary IV construction;
- bandwidth calculation and integer rounding;
- m=1 endpoint semantics;
- duplicate-timestamp provider-order preservation;
- delayed first trade;
- 13:30 closing auction;
- no future information;
- overnight composition;
- invalid/non-finite price failures;
- algorithm identity propagation.

S2 must not use any realized Taiwan panel result to tune these formulas.

## S1 ruling

`TAIWAN_NOISE_ROBUST_BENCHMARK_FAMILY = PARZEN_REALIZED_KERNEL`

`PRIMARY_SOURCE = SHIOAJI_HISTORICAL_TRADE_TICKS`

`FIXED_GRID_5M_10M_15M = COMPARISON_SERIES_ONLY`

`FORECAST_SCORE_SELECTION = FORBIDDEN`

S1 is complete when this memo is committed and read back.

No estimator production code and no new provider call belong to S1.
