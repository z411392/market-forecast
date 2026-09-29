# Taiwan Noise-Robust RV Benchmark — S1 Feasibility Freeze

Task: #90  
Parent measurement task: #12  
Parent empirical evidence: #89  
Upstream XTAI measurement semantics: #86 / PR #88

## S1 ruling

Primary independent Taiwan benchmark:

`NONNEGATIVE_PARZEN_REALIZED_KERNEL_ON_TRANSACTION_TICKS`

Project benchmark identity:

`taiwan-rk-parzen-trades-v1`

Secondary / diagnostic families:

- `TWO_SCALE_RV`: secondary sensitivity only.
- `MSE_OPTIMAL_SPARSE_RV`: diagnostic only.

No estimator was selected from its numerical agreement with 5m, 10m or 15m.
No forecast score was consulted.

## Why realized kernel is primary

The Taiwan fixed-grid pilot in Task #89 is deliberately inconclusive about a canonical
5m / 10m / 15m frequency. The missing piece is an independent estimator designed for
market-microstructure noise.

Barndorff-Nielsen, Hansen, Lunde and Shephard develop realized kernels for estimating
ex-post quadratic variation from noisy high-frequency prices. Their practical implementation
recommends a non-negative Parzen realized kernel, discusses bandwidth selection, endpoint
handling and high-frequency data cleaning, and applies the estimator directly to trade data.

Relevant references:

- Barndorff-Nielsen, Hansen, Lunde & Shephard (2008),
  *Designing Realized Kernels to Measure the ex post Variation of Equity Prices in the Presence of Noise*:
  https://doi.org/10.3982/ECTA6495
- Barndorff-Nielsen, Hansen, Lunde & Shephard (2009),
  *Realized Kernels in Practice: Trades and Quotes*:
  https://doi.org/10.1111/j.1368-423X.2008.00275.x

The practical paper explicitly motivates:

- the non-negative Parzen kernel;
- robustness to serial dependence in market-microstructure noise;
- use with transaction data;
- irregular/endogenous observation times;
- data-driven bandwidth selection;
- endpoint local averaging / jittering;
- careful cleaning of high-frequency observations.

These properties directly match the unresolved Taiwan measurement-identification problem.

## Why the other candidate families are not primary

### Two-scale realized variance

Zhang, Mykland & Aït-Sahalia (2005) propose a two-scale estimator that uses
tick-by-tick data and bias correction for market-microstructure noise:

https://doi.org/10.1198/016214505000000169

It is source-feasible and valuable as an independent formula-level sensitivity measure.

It is not the primary benchmark because the preferred realized-kernel construction has a
direct practical implementation for transaction data and is explicitly robust to serially
dependent noise. The original two-scale construction is therefore retained as a later
secondary sensitivity, not co-equal estimator selection.

### MSE-optimal sparse classical RV

Bandi & Russell (2008) derive an MSE-optimal finite sampling theory for classical realized
variance in the presence of microstructure noise:

https://doi.org/10.1111/j.1467-937X.2008.00474.x

This is useful diagnostically because it provides a theory-driven explanation for why a
fixed 5-minute heuristic need not be universally optimal.

It remains a sparse classical-RV sampling-frequency method. It is therefore not the primary
independent noise-robust benchmark used to identify the Taiwan target.

## Shioaji source feasibility

Official Shioaji historical market data exposes stock tick-by-tick transactions by explicit
date:

https://sinotrade.github.io/tutor/market_data/historical/

Historical `Ticks` provide:

- nanosecond timestamp;
- transaction price (`close`);
- transaction volume;
- bid price / volume;
- ask price / volume;
- tick type.

Official stock history is available from 2020-03-02 through the current date.

This is sufficient for a univariate transaction-price realized kernel.

### Source limitation

The Shioaji historical tick payload does not expose the TAQ-specific fields used by some
cleaning rules in the realized-kernel practical paper, including:

- corrected-trade indicator;
- TAQ sale-condition code.

Therefore a full literal TAQ T1/T2 cleaning replication is impossible from this source and
must not be claimed.

Shioaji does expose bid/ask values on transaction records. A T4-like trade-vs-spread
diagnostic is feasible.

However, historical bid/ask values attached to transaction ticks are not a complete independent
quote-event history. A true full quote-based realized-kernel replication is therefore not part
of the primary benchmark.

## Session semantics

The primary benchmark uses irregular transaction time directly.

### Included intraday observations

For each validated XTAI stock session:

1. first matched whole-share transaction at or after 09:00;
2. all accepted normal-session transactions through 13:25;
3. exact 13:30 closing-auction transaction.

### Excluded observations

Exclude observations after the 13:30 closing auction.

Shioaji historical examples show a 14:30 transaction-like record in addition to the 13:30
close. That after-hours/fixed-price observation is outside the accepted XTAI regular-session
measurement interval and is excluded.

### Opening

The session opening price is the first matched transaction price.

This is consistent with the Task #89 tick evidence and the existing
`SessionOpenPriceObservation` semantics.

### Closing

The final intraday benchmark observation is the exact 13:30 closing-auction transaction.

### No-trade intervals

No calendar-grid interpolation is required for the primary realized kernel.

The benchmark operates on actual transaction observations and therefore does not create:

- synthetic one-minute bars;
- previous-tick calendar samples;
- boundary transactions.

This is intentionally different from the fixed-grid RV path.

## Whole-day benchmark composition

The noise-robust benchmark must remain comparable to the accepted Task #89 whole-day
variance definition.

For session t:

`whole_day_rk_t = intraday_rk_t + overnight_log_return_t^2`

where:

`overnight_log_return_t = log(current_first_matched_trade / previous_13_30_close)`

The overnight term is therefore identical in economic definition to the fixed-grid
5m / 10m / 15m measurements.

Only the intraday estimator changes.

This prevents the benchmark comparison from mixing an intraday-estimator change with a
different overnight convention.

## Source-adapted cleaning freeze

The primary transaction-price cleaning pipeline for S2 is:

1. retain only the accepted XTAI regular-session interval through the exact 13:30 close;
2. reject non-finite transaction prices;
3. reject non-positive transaction prices;
4. require provider timestamps to be non-decreasing;
5. if multiple transactions have the exact same timestamp, replace them with one median
   transaction price for the kernel price sequence;
6. preserve original tick count, retained count, duplicate-collapse count and rejection counts;
7. compute a bid/ask consistency diagnostic when valid positive bid/ask fields are present;
8. never fabricate unavailable correction/sale-condition flags.

The same-timestamp median rule follows the practical realized-kernel trade-data cleaning
principle.

A bid/ask-based hard filter is not frozen in S1. S2 must first freeze deterministic edge-case
oracles, including opening/closing-auction behavior, before deciding whether the T4-like
condition is part of the primary estimator or a cleaning sensitivity.

## Realized-kernel family freeze

Primary kernel:

- Parzen;
- non-negative realized-kernel form;
- transaction log returns;
- irregular/event-time observations.

The practical paper gives the Parzen bandwidth family:

`H* = c* × xi^(4/5) × n^(3/5)`

with:

`c* = 3.5134`

The practical estimator of the noise-to-signal term uses:

- a sparse preliminary realized-variance estimate;
- a dense/subgrid estimate of noise variance;
- q chosen so every q-th observation is approximately two minutes apart.

The paper uses subsampled 20-minute RV for the sparse preliminary variance estimate.

### Not frozen until S2 tests-first

S1 deliberately does not invent unverified implementation details for equations rendered only
in the source paper.

S2 must freeze, with hand-checkable tests before production code:

- exact noise-variance estimator;
- exact sparse-RV offset/subsample construction;
- q integer rule;
- H integer rounding rule;
- endpoint jitter/local-average rule;
- minimum-observation failure rules;
- same-timestamp ordering/collapse behavior;
- non-negative numerical tolerance.

Project preference for ambiguous integer choices is conservative deterministic rounding, but no
choice is production-authorized before S2 RED oracles.

## Endpoint handling

The practical realized-kernel paper uses local averaging / jittering to address end effects and
reports that small m values are empirically similar.

S2 must freeze endpoint behavior before code.

The benchmark must preserve the XTAI economic boundaries:

- first matched transaction at the open side;
- exact 13:30 closing auction at the close side.

Any jittering applies to estimator endpoint construction, not to rewriting the factual market
timestamps.

## Provider traffic feasibility

Official Shioaji limits:

https://sinotrade.github.io/tutor/limit/

For stock accounts with zero 30-day API trading amount:

- daily historical/query traffic allowance: 500 MB;
- `api.usage()` reports used / limit / remaining bytes;
- historical `ticks` and `kbars` are for after-market analysis/backtesting and should not be
  repeatedly polled during trading hours.

A full 3-symbol × 253-session tick panel means 759 AllDay tick queries.

This must not be launched as one blind job.

### Required rollout

The empirical benchmark rollout is frozen as:

1. run a small fixed traffic-calibration pilot across all three symbols;
2. read `api.usage()` before the first query;
3. read `api.usage()` after each bounded batch;
4. record SDK payload byte count and provider-reported traffic delta;
5. derive safe session batch size from observed traffic;
6. preserve a daily safety reserve under the 500 MB cap;
7. stop automatically if the reserve would be crossed;
8. continue on a later day if required;
9. no paid subscription upgrade;
10. no trading action.

Suggested first traffic-calibration cases:

- 2330 / 2024-07-02;
- 2330 / 2026-09-24;
- 2317 / 2025-11-17;
- 2454 / 2026-05-04.

These already have accepted fixed-grid/tick semantics and cover ordinary, parity, delayed-open
and sparse/locked-limit cases.

## Immutable evidence semantics

Shioaji SDK does not expose the network HTTP response bytes at the application boundary used
by this project.

Therefore Task #90 must describe captured evidence accurately as **SDK observation evidence**.

Per provider query persist:

- provider name/version;
- symbol;
- session date;
- exact query type/spec;
- normalized returned payload SHA-256;
- tick count;
- first/last provider timestamp;
- cleaning counts;
- session-boundary classification;
- estimator identity/version;
- kernel;
- bandwidth parameters;
- endpoint parameters;
- intraday RK;
- overnight variance;
- whole-day benchmark variance.

Do not label SDK-serialized payload bytes as network-raw provider bytes.

## Estimator identity

Initial benchmark identity reserved by S1:

`taiwan-rk-parzen-trades-v1`

This identity is not final production acceptance.

It becomes executable only after S2 freezes exact estimator/cleaning parameter oracles and
production code passes them.

## S1 exit criteria

Completed:

- benchmark family selected independently of fixed-grid numerical results;
- source data requirements identified;
- historical source availability verified;
- session semantics frozen;
- overnight composition frozen;
- source cleaning capabilities/limitations documented;
- provider-traffic rollout bounded;
- evidence semantics defined;
- estimator version namespace reserved.

Not completed:

- exact RK formula implementation;
- exact bandwidth/jitter integer rules;
- production code;
- provider traffic pilot;
- 3-symbol empirical RK panel;
- Taiwan canonical target freeze.

## Next bounded slice

Task #90 S2a only:

- create contract/DTO oracles for cleaned transaction observations and daily realized-kernel
  output;
- freeze exact Parzen kernel weight math and autocovariance summation with tiny hand-computable
  sequences;
- do not implement bandwidth selection in the same slice;
- no provider call.

Subsequent S2 slices should freeze bandwidth/noise estimation and endpoint handling separately
before production implementation.
