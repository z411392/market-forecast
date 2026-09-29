# Task 90 — Taiwan Noise-Robust Benchmark Feasibility Freeze

Task: #90  
Parent measurement task: #12  
Depends on: #89 accepted Taiwan v4 pilot, #86 XTAI v4 semantics candidate

## S1 ruling

`TAIWAN_NOISE_ROBUST_PRIMARY = PARZEN_REALIZED_KERNEL_ON_TRANSACTION_TICKS`

Source ruling:

`SHIOAJI_TICKS_API_SHAPE_FEASIBLE / FULL_PANEL_BANDWIDTH_CALIBRATION_PENDING`

This memo freezes the estimator family and source boundary only.

It does not:
- implement the estimator;
- fetch new provider data;
- select realized-kernel bandwidth from empirical Taiwan results;
- freeze 5m/10m/15m;
- use forecast QLIKE/model performance.

## Decision context

Task #89 completed the 3-symbol × 252-session Taiwan fixed-grid audit under:

`rv-core-v1+xtai-closing-auction-v4`.

The fixed-grid decision was:

`TAIWAN_CANONICAL_SAMPLING = INCONCLUSIVE`.

The empirical panel has:
- high 5m/10m/15m log/rank agreement;
- systematic double-digit 5m-vs-coarser level sensitivity;
- no independent latent-variance truth criterion.

An independent noise-robust estimator is therefore needed before Taiwan canonical target freeze.

## Candidate comparison

### Parzen realized kernel — primary benchmark

Role:
- independent daily intraday variation benchmark;
- robust to market microstructure noise by estimator construction;
- based on transaction observations rather than one chosen 5m/10m/15m sparse grid.

Input:
- cleaned Shioaji transaction ticks;
- tick-time / irregular observation sequence;
- first matched transaction through the 13:30 closing-auction transaction.

Reason for selecting Parzen RK:
- realized kernels are a direct ex-post variation estimator under market microstructure noise;
- realized-kernel practice explicitly supports transaction-trade input;
- empirical realized-kernel work includes estimators based on all available trades;
- the estimator does not need a canonical 5m/10m/15m grid in order to exist.

The precise feasible bandwidth, endpoint treatment and kernel formula are S2 tests-first decisions and must be frozen before Taiwan empirical comparison.

### TSRV / MSRV — secondary estimator sensitivity

Status:
`FEASIBLE / NOT PRIMARY`.

Reason:
- directly relevant noise-robust family;
- useful as an independent sensitivity estimator after the primary RK contract is fixed;
- introduces extra scale/subsampling and finite-sample choices;
- those choices increase researcher degrees of freedom if used as the first benchmark.

TSRV/MSRV must not be tuned after seeing which fixed-grid frequency it favors.

### MSE-optimal classical-RV sampling — diagnostic only

Status:
`DIAGNOSTIC / NOT DAILY BENCHMARK`.

Aït-Sahalia/Mykland/Zhang and Bandi/Russell motivate finite MSE-optimal sparse sampling under microstructure noise.

That provides a useful diagnostic about whether 5m is plausibly too fine or too coarse.

It does not by itself provide the independent daily latent-variation benchmark required by Task #90 S3.

## Why historical transaction ticks are required for the primary benchmark

Shioaji historical Kbars are adequate for the accepted fixed-grid measurement path.

They are not the preferred primary noise-robust benchmark input because they already:
- aggregate all transactions inside each minute;
- discard within-minute price/noise dynamics;
- omit zero-trade minutes;
- require the previous-tick/fixed-grid synchronization semantics already being audited.

Using transaction ticks preserves within-minute information and keeps benchmark construction independent of the final 5m/10m/15m choice.

One-minute Kbars remain useful for:
- the fixed-grid comparator;
- XTAI session-semantic cross-checks;
- replay/debug evidence.

## Shioaji source feasibility

Official Shioaji historical market data supports:
- stock transaction ticks;
- historical period from 2020-03-02 to current;
- `api.ticks(..., query_type=AllDay)` for one trading day;
- timestamp;
- transaction price;
- transaction volume;
- bid/ask fields;
- tick type.

The accepted Taiwan panel contains:
- 3 symbols;
- 252 audit sessions;
- therefore 756 symbol-day tick queries for a full tick benchmark panel.

Official query-rate limit:
- market-data queries up to 50 calls per 10 seconds.

Official stock data allowance:
- baseline daily bandwidth is 500MB when recent API trading turnover is zero.

The query count is operationally feasible with conservative pacing.

Full-panel bandwidth is not yet proven and is intentionally not guessed from current evidence.

Before full S3 collection, run a separate bounded traffic calibration.

## Future traffic-calibration requirement

Required before a 756-day tick collection:

1. select a tiny representative set covering:
   - high activity;
   - normal activity;
   - low/locked/no-trade activity;
   - all three pilot symbols where possible;
2. read Shioaji usage before collection;
3. fetch only the frozen representative tick-days;
4. read Shioaji usage after collection;
5. record incremental provider bytes;
6. estimate bytes/tick-day and a conservative resumable daily batch size;
7. cap collection well below the account's daily bandwidth limit;
8. cache each accepted day separately so interrupted work never restarts the full panel.

No traffic calibration belongs to S1.

## Tick-time synchronization rule

Primary RK benchmark uses transaction-time observations.

It does not previous-tick regularize transaction data onto a 1-second or 1-minute calendar grid.

This deliberately separates the noise-robust benchmark from the fixed-grid estimator under audit.

## Deterministic tick-cleaning freeze

S2 implementation must start from this deterministic cleaning contract.

For each symbol/session:

1. require one provider session date;
2. retain the XTAI regular session from the first matched transaction through the 13:30 closing-auction transaction;
3. require non-decreasing provider timestamps;
4. reject non-finite or non-positive transaction prices;
5. reject non-positive transaction volume;
6. when multiple transactions share the exact same timestamp:
   - replace them with the median transaction price for that timestamp;
   - record the duplicate group size/count;
7. do not create transactions at missing times;
8. do not previous-tick fill the tick-time benchmark;
9. do not introduce an empirical/post-hoc return-outlier threshold in v1.

The same-timestamp median policy is consistent with published high-frequency cleaning practice derived from Barndorff-Nielsen et al. and Hansen/Lunde.

Shioaji does not expose the complete TAQ trade-correction/sale-condition metadata used by some U.S. cleaning protocols.

Filters that depend on unavailable TAQ fields must not be silently approximated.

## Session endpoints

### Open

Use the first matched transaction of the current session.

This is consistent with the TWSE opening-price definition already established by Task #89.

Do not create a 09:00 transaction when the first match occurs later.

### Close

Include the actual 13:30 closing-auction transaction as the terminal intraday observation.

A missing validated 13:30 closing observation remains fail-closed.

## Whole-day benchmark composition

Primary benchmark whole-day variance:

`whole_day_rk = intraday_realized_kernel + overnight_log_return^2`

where overnight log return is:

`log(current first matched opening price / previous validated 13:30 closing price)`.

This preserves Task #86/#89 whole-day semantics while changing only the intraday measurement estimator.

## Evidence boundary

Shioaji SDK exposes decoded tick arrays, not raw HTTP response bytes.

For every collected symbol-day, persist:

- provider;
- provider SDK version;
- symbol;
- session date;
- deterministic request identity;
- deterministic normalized SDK tick payload bytes;
- SHA-256 of normalized SDK tick payload;
- deterministic cleaned tick sequence;
- SHA-256 of cleaned tick sequence;
- input tick count;
- retained tick count;
- same-timestamp duplicate-collapse diagnostics;
- opening/closing identity;
- estimator version/parameters;
- final estimator result.

Never label SDK-decoded bytes as a raw network response.

Each symbol-day artifact must be independently addressable and resumable.

## Estimator identity boundary

S1 freezes the family, not the final formula parameters.

S2 must freeze, before empirical Taiwan comparison:

- exact Parzen kernel function;
- exact autocovariance convention;
- exact feasible bandwidth / plug-in rule;
- exact endpoint/jittering treatment;
- minimum observation count;
- same-timestamp median implementation;
- numerical precision/tolerance;
- estimator version string.

Suggested identity namespace:

`taiwan-rk-parzen-tick-v1`

Do not finalize that version as accepted until S2 mathematical oracles are green.

## Forbidden parameter selection

The following may not select RK bandwidth or cleaning choices:

- closeness to Taiwan 5m RV;
- closeness to Taiwan 10m RV;
- closeness to Taiwan 15m RV;
- HAR/GARCH/HARQ/forecast QLIKE;
- later 30+30 model performance.

Parameter choices must come from the estimator literature and deterministic source constraints.

## S1 completion criteria

Completed:

- primary estimator family selected;
- primary source type selected;
- 1m-Kbar-only benchmark rejected as primary;
- secondary estimator roles defined;
- transaction-time synchronization frozen;
- opening/closing/overnight semantics frozen;
- immutable/resumable evidence boundary frozen;
- query-count feasibility established from official API shape.

Still pending:

- exact RK mathematical parameterization;
- bounded tick-traffic calibration;
- production estimator implementation;
- full 3×252 tick benchmark;
- comparison to fixed-grid measurements;
- final Taiwan canonical target freeze.

## References

Measurement theory:

- Barndorff-Nielsen, Hansen, Lunde & Shephard (2008), *Designing Realized Kernels to Measure the Ex-Post Variation of Equity Prices in the Presence of Noise*.
- Barndorff-Nielsen, Hansen, Lunde & Shephard (2009), *Realized Kernels in Practice: Trades and Quotes*.
- Aït-Sahalia, Mykland & Zhang (2005), *How Often to Sample a Continuous-Time Process in the Presence of Market Microstructure Noise*.
- Zhang, Mykland & Aït-Sahalia (2005), two-scale realized volatility.
- Bandi & Russell (2008), *Microstructure Noise, Realized Variance, and Optimal Sampling*.

Source documentation:

- https://sinotrade.github.io/zh/tutor/market_data/historical/
- https://sinotrade.github.io/zh/tutor/limit/

## Next bounded slice

S2a only:

- freeze the mathematical Parzen realized-kernel contract on synthetic transaction sequences;
- add tests first;
- prove RED;
- do not call Shioaji;
- do not implement traffic calibration in the same slice.
