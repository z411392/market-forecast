# Task #90 S4a — Shioaji Tick Acquisition and Traffic Calibration Contract

Task: #90  
Parent: #12  
Branch: `codex/90-taiwan-rk-feasibility`  
Estimator: `tw-rk-parzen-trades-v1`

## Scope

This slice freezes provider acquisition, provenance and traffic-stop behavior for the Taiwan Parzen realized-kernel benchmark.

It does **not** implement the full 3-symbol × 252-session tick collector and does not compute empirical benchmark results.

## Authoritative branch reconciliation

The current Task #90 branch artifacts/tests are authoritative over earlier research-comment drafts.

Final accepted S1/S2/S3 contract:

- same-timestamp trades preserve provider order;
- no same-timestamp median collapse;
- endpoint jitter parameter `m = 2`;
- primary estimator input is transaction ticks;
- fixed-grid previous-tick synchronization is used only by the bandwidth sparse-RV plug-in, not by the primary realized-kernel return sequence.

## Provider version

Calibration pins:

`shioaji==1.7.6`

Official release date: 2026-09-22.

## Historical tick request

Exactly one symbol and one session per request:

```python
api.ticks(
    contract=contract,
    date=session_date,
    query_type=sj.constant.TicksQueryType.RangeTime,
    time_start="09:00:00",
    time_end="13:30:59",
)
```

Reason for RangeTime:

- estimator scope is the XTAI regular session;
- first actual matched trade may occur after 09:00;
- 13:30 closing-auction transaction is included;
- unrestricted AllDay data is not the estimator input.

## Required provider fields

The normalized SDK observation artifact retains provider-order arrays for:

- `ts`;
- `close`;
- `volume`;
- `bid_price`;
- `bid_volume`;
- `ask_price`;
- `ask_volume`;
- `tick_type`.

The estimator input itself uses validated transaction prices, but quote/tick-type fields remain immutable provenance.

## Validation

Each response must satisfy:

- all required fields exist;
- equal field lengths;
- at least one transaction;
- timestamp date equals requested session date;
- timestamp local wall-clock lies inside 09:00:00–13:30:59;
- timestamps are non-decreasing;
- transaction price is finite and strictly positive;
- volume is strictly positive;
- first transaction is retained as the factual opening observation;
- at least one transaction exists during the 13:30 minute;
- provider order is retained for equal timestamps.

No:

- price smoothing;
- outlier deletion;
- same-price deduplication;
- same-timestamp collapse;
- synthetic transaction;
- calendar-time resampling in the primary tick sequence.

## Deterministic evidence

Per symbol/session persist:

1. exact request spec;
2. provider version;
3. normalized SDK payload bytes and SHA-256;
4. validated estimator transaction sequence bytes and SHA-256;
5. tick count;
6. first / last timestamps;
7. opening transaction;
8. terminal 13:30 transaction;
9. equal-timestamp adjacency count;
10. provider traffic usage before / after and measured byte delta.

These are **SDK observation artifacts**, not raw network-response bytes.

## Traffic policy

Current official baseline stock allowance for an account with zero recent API trading amount is 500MB/day.

Frozen Task #90 conservative guard:

- minimum provider-reported remaining bytes before any calibration query:
  `250 MiB`;
- stop if provider-reported remaining bytes falls below `250 MiB`;
- stop if cumulative Task #90 current-run provider-byte delta reaches `250 MiB`;
- no automatic retry on empty/error response;
- one login / one connection per process;
- calibration requests are sequential, not burst/polled;
- accepted symbol-day artifacts are cacheable/resumable and must not be blindly re-queried.

A future full-panel collector must enforce the same guards and skip already accepted cached symbol-days.

## Tiny calibration matrix

Exactly three requests:

| Symbol | Session | Role |
|---|---|---|
| 2330 | 2026-09-24 | active normal reference |
| 2317 | 2026-09-24 | normal reference |
| 2454 | 2026-05-04 | low-activity / locked-limit stress case |

This sample is traffic calibration only. It is not sufficient for realized-kernel empirical conclusions.

## Calibration outputs

Report:

- provider daily `limit_bytes`;
- baseline / final `bytes` and `remaining_bytes`;
- per query traffic delta;
- ticks per query;
- bytes per tick;
- median / max bytes per tick-day across the three calibration cases;
- naïve 759-query projection using median and maximum measured tick-day delta.

Projection is a planning diagnostic only. It does not authorize a full run.

## Full-panel implications

Current upper-bound evidence window:

- 3 symbols;
- 253 symbol/session tick-days if retaining one prior day for first overnight construction;
- 759 date-scoped historical tick requests.

Before a full acquisition run:

- inspect current provider usage;
- determine a safe batch size from calibration;
- shard across executions/days when the conservative 250MiB guard would otherwise be crossed;
- persist every completed symbol-day independently;
- never restart from day zero after interruption.

## Sources

- Shioaji historical market data:
  https://sinotrade.github.io/zh/tutor/market_data/historical/
- Shioaji limits / `api.usage()`:
  https://sinotrade.github.io/zh/tutor/limit/
- Shioaji releases:
  https://sinotrade.github.io/release/
- Barndorff-Nielsen, Hansen, Lunde & Shephard, *Realized Kernels in Practice: Trades and Quotes*:
  https://doi.org/10.1111/j.1368-423X.2008.00275.x

## S4a stop boundary

After the three-query calibration:

- persist traffic/evidence results;
- do not start the full tick panel;
- do not compute benchmark-vs-fixed-grid comparison;
- stop and make the next bounded collection-plan decision from measured traffic.
