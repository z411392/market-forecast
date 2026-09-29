# Taiwan Noise-Robust RV Benchmark — S1 Feasibility Freeze

Task: #90  
Parent measurement task: #12  
Depends on: #89 accepted Taiwan v4 panel, #86 XTAI v4 semantics

## S1 ruling

`ESTIMATOR_SELECTED / 1M_KBARS_SUFFICIENT / BULK_TICKS_NOT_REQUIRED`

Primary benchmark identity:

`taiwan-parzen-rk-1m-v1`

The primary benchmark is a non-negative Parzen realized kernel built from the accepted
Shioaji one-minute evidence and Task #86 v4 previous-tick provenance semantics.

This selection is frozen before any realized-kernel comparison against 5m / 10m / 15m
fixed-grid results.

## Why realized kernel is primary

The fixed-grid Taiwan audit has high rank/log agreement but persistent level sensitivity.
A useful benchmark therefore needs to estimate ex-post variation under microstructure noise
without selecting a target merely by choosing another sparse fixed grid.

The Parzen realized-kernel family is preferred because it:

- is explicitly designed for high-frequency prices contaminated by microstructure noise;
- uses lagged return autocovariances rather than relying only on sparse sampling;
- supports serially dependent noise under broad conditions;
- has a non-negative Parzen implementation;
- has a published practical implementation procedure;
- has published empirical use on one-minute returns as well as transaction/quote data.

Primary literature:

- Barndorff-Nielsen, Hansen, Lunde & Shephard (2008), *Designing Realized Kernels to
  Measure the ex post Variation of Equity Prices in the Presence of Noise*.
  https://ideas.repec.org/a/ecm/emetrp/v76y2008i6p1481-1536.html
- Barndorff-Nielsen, Hansen, Lunde & Shephard (2009), *Realized kernels in practice:
  trades and quotes*.
  https://academic.oup.com/ectj/article-abstract/12/3/C1/5061260
- Practical implementation PDF:
  https://faculty.washington.edu/ezivot/econ589/realizedKernelsInPractice.pdf

## Candidate-family disposition

### Primary — Parzen realized kernel

Use as the independent Taiwan measurement benchmark.

Reasons:

- theory directly addresses noisy high-frequency observations;
- non-negative output is desirable for a variance target;
- feasible from accepted one-minute evidence;
- does not require choosing 5m, 10m, or 15m as the benchmark grid.

### Secondary sensitivity — two-scale / multi-scale realized variance

Retain as a later robustness estimator, not the initial benchmark.

It is theoretically noise-robust, but introduces another scale/subgrid design. Adding it before
the primary benchmark is implemented would increase the number of measurement choices before
the identification problem is narrowed.

Reference:

- Aït-Sahalia, Mykland & Zhang, *Ultra High Frequency Volatility Estimation with
  Dependent Microstructure Noise*.
  https://galton.uchicago.edu/~mykland/paperlinks/depnoise.pdf

### Diagnostic only — MSE-optimal classical-RV sampling

Bandi-Russell optimal sampling is useful as a diagnostic of the noise/discretization trade-off,
but not as the sole independent benchmark because its output is still a preferred sparse
classical-RV sampling interval.

Reference:

- Bandi & Russell (2008), *Microstructure Noise, Realized Variance, and Optimal Sampling*.
  https://academic.oup.com/restud/article-abstract/75/2/339/1620899

## Source feasibility

### Primary panel source

Use Shioaji historical 1-minute Kbars.

Bulk tick history is not required for the primary benchmark.

Task #89 already established with targeted tick checks that:

- an emitted historical stock Kbar is end-labelled;
- its OHLC matches the corresponding factual transaction minute;
- absent Kbars can represent true zero-trade intervals;
- official opening price can be represented separately;
- the 13:30 auction is a distinct observation;
- previous-tick sampling can carry a factual earlier price without creating a synthetic minute bar.

The realized-kernel practice literature also reports realized kernels computed from one-minute
returns, so a one-minute input is not being introduced only for provider convenience.

Shioaji documentation:

- Historical Ticks / Kbars:
  https://sinotrade.github.io/zh/tutor/market_data/historical/
- Current usage / traffic limits:
  https://sinotrade.github.io/zh/tutor/limit/

### Raw-evidence availability

Task #89 persisted chunk hashes and audit summaries, but did not persist the complete normalized
3-symbol × 253-session Kbar payload.

Therefore S3 must use either:

1. an externally cached raw panel whose hashes match the Task #89 identities; or
2. one bounded Kbar recapture.

Expected recapture bound:

- 3 symbols;
- <=28 calendar days per chunk;
- approximately 14 chunks/symbol;
- approximately 42 Kbar queries total;
- no per-session AllDay tick loop.

Every recaptured normalized chunk must be hashed and cached before estimator calculation.

## Continuous-session price construction

The realized kernel estimates the continuous-session variation.

### Opening

Use `SessionOpenPriceObservation.price` as the initial factual opening price.

Do not assign a fabricated 09:00 transaction time.

If the first trade occurs after 09:00, pre-first-trade grid boundaries without a factual prior
price are omitted rather than filled.

### One-minute grid

After the first factual price is available, construct a one-minute exchange-clock price sequence
through 13:25 local.

At each one-minute boundary:

- use the factual Kbar Close if a trade-bearing bar ends at that boundary;
- otherwise use previous-tick CTS from the most recent factual trade-bearing observation;
- preserve source interval and staleness bounds;
- do not create a canonical minute bar;
- do not claim a transaction occurred at the grid boundary.

### Closing auction

The 13:30 closing auction is not inserted as an ordinary one-minute kernel observation.

Define separately:

`r_close = log(P_13:30_auction / P_13:25_grid)`

and:

`closing_auction_variance = r_close^2`.

### Overnight

Use the existing accepted definition:

`r_overnight = log(P_open_today / P_close_auction_previous_session)`.

Whole-day benchmark:

`whole_day_rk = r_overnight^2 + RK_continuous_session + r_close^2`.

## Parzen realized-kernel definition

For continuous-session log returns `r_1, ..., r_n`:

`gamma_h = sum_{j=h+1..n} r_j * r_{j-h}`

and:

`RK = gamma_0 + 2 * sum_{h=1..H} k(h / (H + 1)) * gamma_h`.

Parzen weight:

`
k(x) =
  1 - 6x^2 + 6x^3,  0 <= x <= 1/2
  2(1-x)^3,          1/2 < x <= 1
  0,                 x > 1
`.

## Endpoint treatment

Freeze local endpoint averaging at:

`m = 2`.

For the continuous-session log-price sequence:

- effective first endpoint = mean of the first two available log prices;
- effective last endpoint = mean of the final two continuous-session log prices;
- interior observations remain unchanged.

The closing auction is outside this endpoint treatment.

The practical realized-kernel literature reports that endpoint averaging addresses end effects
and uses m=2 in its empirical implementation.

## Bandwidth selection

Freeze the primary plug-in bandwidth:

`H* = ceil(3.5134 * xi_hat^(4/5) * n^(3/5))`.

Use:

`xi_hat^2 = omega_hat^2 / IV_hat`.

### Noise estimate

For the accepted one-minute grid:

`omega_hat^2 = RV_dense_1m / (2 * n_nonzero_returns)`.

This is the q=1 noise estimate. q>1 is used in the tick implementation for robustness, but
one-minute bars are the frozen source for v1.

### Preliminary IV

Use a 20-minute sparse realized-variance estimate averaged over all 20 available one-minute
phase offsets.

This is an explicit one-minute-source adaptation of the practical paper's tick-data procedure,
which averages 20-minute RV over one-second shifts.

This adaptation is part of the estimator version and must not be hidden.

### Validity clamp

Require:

`1 <= H < n`.

A session fails closed if the plug-in components are non-finite, non-positive where required,
or cannot produce a valid bandwidth.

## Parameter sensitivity frozen before empirical comparison

S3 must also calculate deterministic bandwidth sensitivity:

- `H_low = floor(0.75 * H*)`;
- `H_primary = H*`;
- `H_high = ceil(1.25 * H*)`;

with all values clamped to `[1, n-1]`.

These sensitivity values are frozen now and may not be changed after seeing which version is
closest to 5m / 10m / 15m.

## Required estimator identity

Every benchmark output must carry at least:

- estimator version: `taiwan-parzen-rk-1m-v1`;
- source provider / exchange;
- source price basis;
- Task #86 XTAI semantics identity;
- grid construction identity;
- previous-tick provenance identity;
- Parzen kernel identity;
- endpoint jitter `m=2`;
- `omega_hat^2`;
- `IV_hat`;
- `xi_hat`;
- selected `H*`;
- sensitivity bandwidths;
- continuous-session RK;
- closing-auction variance;
- overnight variance;
- whole-day benchmark variance.

## Fail-closed rules

- no future session information;
- no forecasting score or QLIKE;
- no benchmark selection after comparison to 5m / 10m / 15m;
- no synthetic transaction claims;
- no synthetic one-minute OHLCV bars;
- no silent session deletion;
- no non-finite / negative whole-day variance;
- source/session semantics must remain consistent with Task #86 v4;
- estimator parameters must be reproducible from the same input prices.

## S2 boundary

Next slice is tests-first implementation only.

S2 should freeze deterministic unit/contract oracles for:

1. one-minute price-grid construction with previous-tick provenance;
2. Parzen weights;
3. realized autocovariances;
4. endpoint m=2 transformation;
5. q=1 noise estimate;
6. 20-offset sparse-IV preliminary estimate;
7. plug-in bandwidth;
8. realized kernel;
9. closing-auction + overnight whole-day composition;
10. invalid/session-edge cases.

No Shioaji call is required in S2.

S3 provider-backed comparison must wait until S2 is GREEN.
