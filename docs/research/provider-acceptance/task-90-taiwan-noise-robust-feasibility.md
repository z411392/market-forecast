# Taiwan Noise-Robust Benchmark Feasibility

Task: #90  
Parent measurement task: #12  
Upstream Taiwan evidence: #89  
Upstream XTAI measurement semantics: #86 / PR #88

## S1 ruling

`TAIWAN_NOISE_ROBUST_BENCHMARK = PARZEN_REALIZED_KERNEL_ON_TRADE_TICKS`

Estimator identity:

`tw-rk-parzen-trades-v1`

This selection is based on measurement theory and provider/source feasibility only.

It is not selected because of numerical proximity to the existing 5m, 10m or 15m realized-variance series, and forecast-model performance is not part of the decision.

## Why a realized kernel

The accepted Taiwan fixed-grid pilot shows high rank/log agreement across 5m, 10m and 15m while retaining systematic double-digit level sensitivity. That means the next benchmark should estimate ex-post variation under microstructure noise without simply selecting one of those sparse grids.

The realized-kernel family is designed for this purpose.

The primary benchmark is the non-negative Parzen realized kernel described by Barndorff-Nielsen, Hansen, Lunde and Shephard.

Reasons for selecting it as the primary benchmark:

- noise-robust high-frequency variance estimator;
- practical implementation guidance exists for transaction data;
- Parzen weights produce a non-negative estimator;
- the source can be actual historical transaction ticks;
- it does not reuse the same fixed-grid measurement transform being audited;
- current repository dependencies already contain NumPy/SciPy, so no new statistical runtime dependency is required.

## Why transaction ticks are the primary source

Shioaji historical market data supports both tick-by-tick trades and minute Kbars.

The benchmark will use transaction ticks.

Using 1m Kbars as the primary noise-robust benchmark would already discard within-minute trade information and would partially inherit the fixed-grid/previous-tick processing whose level sensitivity is the object under investigation.

The accepted 1m Kbar path remains useful for:

- source/session cross-checking;
- comparison to the existing Task #86 measurement semantics;
- fallback diagnostics.

It is not the primary realized-kernel input.

## Provider query contract

Do not use unrestricted `AllDay` output as the estimator input.

Shioaji examples can contain observations later than the 13:30 regular-session close.

Frozen query shape:

```python
api.ticks(
    contract=contract,
    date=session_date,
    query_type=sj.constant.TicksQueryType.RangeTime,
    time_start="09:00:00",
    time_end="13:30:59",
)
```

One provider request corresponds to exactly one symbol and one session.

The returned records are still validated against the requested local session date/window before use.

## Tick validation and cleaning

Preserve provider order.

Required:

- timestamp belongs to the requested session date/window;
- timestamps are non-decreasing;
- transaction price is finite and strictly positive;
- volume is strictly positive;
- at least one regular-session trade exists;
- first transaction is the official opening trade observation;
- a 13:30 closing-auction transaction is present.

Retain in provider evidence:

- timestamp;
- transaction price;
- volume;
- bid price / volume;
- ask price / volume;
- tick type.

Estimator input uses transaction log prices.

Bid/ask and tick-type fields are retained for provenance and diagnostics; they are not used to tune the estimator after results are observed.

Do not:

- remove a transaction because its price looks unusual;
- deduplicate same-price transactions;
- smooth prices;
- invent sale-condition flags unavailable from Shioaji;
- create synthetic transactions.

## Session endpoints

Opening price:

- actual first matched transaction returned in the regular-session tick stream;
- no fabricated 09:00 trade timestamp.

Closing price:

- final regular-session closing-auction transaction in the 13:30 minute.

The exact first/last transaction timestamps and prices remain in evidence.

The realized-kernel estimator uses endpoint jittering as an estimator transformation; this does not rewrite the factual session open/close evidence.

## Whole-day benchmark

For session t:

```text
whole_day_noise_robust_variance_t
    = intraday_realized_kernel_t
    + overnight_log_return_t^2
```

where overnight return is:

```text
log(current_session_first_trade_price / previous_validated_13_30_close)
```

This keeps the benchmark comparable to the whole-day Task #89 5m/10m/15m measurements.

## Realized-kernel formula

For high-frequency log-price returns `x_j`:

```text
gamma_h = sum_{j=h+1..n} x_j * x_{j-h}

RK = gamma_0
     + 2 * sum_{h=1..H} k(h / (H + 1)) * gamma_h
```

Parzen weight:

```text
k(x) = 1 - 6 x^2 + 6 x^3        for 0 <= x <= 1/2
     = 2 (1 - x)^3              for 1/2 < x <= 1
     = 0                        otherwise
```

## End effects

Freeze endpoint jittering to:

`m = 2`

The first and last estimator log-price observations are local averages of the first two and last two raw log prices, following the practical realized-kernel implementation.

Actual first/last transactions remain unchanged in evidence and remain the source for overnight/open-close identity.

## Bandwidth

Use the Parzen plug-in bandwidth:

```text
H_hat = ceil(3.5134 * xi_hat^(4/5) * n^(3/5))
```

with a final clamp to the valid autocovariance range.

The practical plug-in follows the published procedure:

### Sparse IV proxy

`RV_sparse` is based on 20-minute calendar-time realized variance, averaged across one-second phase shifts.

Transaction prices are synchronized to those sparse calendar times by previous-tick observation.

This previous-tick construction is used only for the bandwidth plug-in calculation; the realized-kernel return sequence itself remains transaction-time.

### Noise variance

Estimate microstructure-noise variance from transaction subgrids.

Choose q so that every q-th transaction is approximately two minutes apart on average.

For each of the q starting offsets:

```text
omega2_i = RV_dense_i / (2 * nonzero_return_count_i)
```

Then:

```text
omega2_hat = mean(omega2_i)
```

Use:

```text
xi_hat^2 = omega2_hat / RV_sparse
```

for the practical bandwidth calculation.

All parameter formulas and rounding conventions must be frozen in S2 tests before production implementation.

## Previous-tick boundary

Previous-tick does not define the primary realized-kernel return series.

The primary estimator uses the irregular transaction sequence directly.

Previous-tick appears only in:

- the sparse calendar-time RV used by the bandwidth plug-in;
- the existing fixed-grid Task #86/Task #89 comparator measurements.

This makes the benchmark structurally independent of the 5m/10m/15m fixed-grid transform.

## Alternative candidates

### Two-scale / multi-scale realized variance

Feasible from Shioaji high-frequency data and retained as a possible sensitivity estimator.

Not selected as the primary S2 implementation because:

- basic TSRV is less asymptotically efficient than the preferred realized-kernel construction;
- two-scale bias correction can produce awkward finite-sample behavior;
- it does not provide the same non-negative estimator guarantee as the Parzen realized kernel.

### MSE-optimal classical-RV sampling

Useful as a secondary diagnostic of optimal sparse-grid spacing.

It is not itself an independent noise-robust daily variance benchmark, so it cannot alone resolve the benchmark requirement in #90.

## Source traffic

Shioaji historical tick queries consume traffic.

The documented stock traffic limit for an account with zero 30-day API trading amount is 500MB/day.

The complete Taiwan pilot contains:

- 3 symbols;
- 252 benchmark sessions;
- 756 symbol-session tick requests.

Do not launch all 756 requests blindly.

Before full S3 acquisition:

1. execute a predeclared traffic-calibration sample;
2. record `api.usage()` before and after each calibration query;
3. cache every returned payload;
4. project full-panel bytes;
5. shard the full acquisition across runs/days if needed;
6. stay materially below the daily provider traffic ceiling.

No provider call belongs to S1.

## Evidence identity

For each symbol/session tick response, later acquisition must persist:

- deterministic provider-order serialization;
- SHA-256;
- provider version;
- exact request spec;
- tick count;
- first/last timestamps;
- opening transaction;
- 13:30 closing transaction;
- traffic delta.

The Shioaji SDK output must be described as an SDK observation artifact, not as raw HTTP response bytes.

## Implementation boundary

S2 may now proceed tests-first.

S2 should freeze:

- estimator DTO identity;
- Parzen weight oracles;
- realized-autocovariance convention;
- m=2 endpoint jittering;
- plug-in bandwidth parameter DTO/calculation;
- fail-closed invalid-price/time/input cases;
- deterministic benchmark version identity;
- whole-day overnight composition.

S2 must not query Shioaji.

## References

- Barndorff-Nielsen, Hansen, Lunde & Shephard, *Realized Kernels in Practice: Trades and Quotes*  
  https://onlinelibrary.wiley.com/doi/10.1111/j.1368-423X.2008.00275.x

- Barndorff-Nielsen, Hansen, Lunde & Shephard, *Designing Realized Kernels to Measure the Ex-Post Variation of Equity Prices in the Presence of Noise*  
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=620203

- Zhang, Mykland & Aït-Sahalia, *A Tale of Two Time Scales*  
  https://www.nber.org/papers/w10111

- Bandi & Russell, *Microstructure Noise, Realized Variance, and Optimal Sampling*  
  https://academic.oup.com/restud/article-abstract/75/2/339/1620899

- Shioaji historical market data  
  https://sinotrade.github.io/zh/tutor/market_data/historical/

- Shioaji usage restrictions  
  https://sinotrade.github.io/zh/tutor/limit/
