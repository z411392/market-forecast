# Task #14 — GOOGL TradingView Runtime Parity Check

Status: RUNTIME_PARITY_EVIDENCE

## Inputs

New HAR-primary export:

- file: `BATS_GOOGL, 1D(8).csv`
- rows: 2,410
- date range: 2017-02-24 through 2026-09-25

Historical Phase 4A export:

- file: `BATS_GOOGL, 1D(7).csv`
- rows: 2,380
- overlapping date range: 2017-04-07 through 2026-09-25

## Exact parity on overlapping rows

| New HAR-primary field | Phase 4A field | Finite overlap | Max absolute difference |
|---|---|---:|---:|
| `RF_INTRABAR_COUNT_5M` | `P4_INTRABAR_COUNT_5M` | 2,380 | 0.0 |
| `RF_RV_WHOLE_DAY_5M` | `P4_RV_WHOLE_DAY_5M` | 1,361 | 0.0 |
| `RF_FORECAST_HAR_VAR5` | `P4_FORECAST_HAR_LEVEL_VAR5` | 329 | 0.0 |
| `RF_HAR_VOL5_ANNUALIZED_PCT` | `P4_HAR_VOL5_ANNUALIZED_PCT` | 329 | 0.0 |
| `RF_QLIKE_HAR` | `P4_QLIKE_HAR` | 324 | 0.0 |
| `RF_QLIKE_252_HAR` | `P4_QLIKE_252_HAR` | 73 | 0.0 |

The visible main plot `HAR 5D Expected Volatility %` is also exactly identical to
`RF_HAR_VOL5_ANNUALIZED_PCT` on all 329 finite rows.

## Current GOOGL output

On 2026-09-25:

- intrabar count: 78
- whole-day RV: 0.000229
- H=5 HAR variance forecast: 0.000417
- annualized expected volatility: 32.4181%
- 5D one-sigma move: 4.5664%
- trailing 252-observation HAR QLIKE: 0.210411

## Ruling

The HAR-primary simplification preserves the historical Phase 4A HAR computation exactly on GOOGL.

This provides actual TradingView runtime/export evidence in addition to static source inspection:

- Pine v6 compiled and executed sufficiently to produce the export.
- HAR-primary source did not alter 5m RV, whole-day RV, HAR forecast, annualization, or matured QLIKE.
- removal of GARCH/HARQ from the daily-use artifact does not change the retained HAR path.

This is one-symbol runtime parity evidence. It does not by itself prove cross-symbol Pine parity, but it removes the primary
risk that the simplified HAR-primary artifact accidentally changed the retained HAR calculation.
