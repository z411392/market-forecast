# Task #90 — Taiwan canonical measurement decision

Status: `ACCEPTED / FINAL`

## Decision

`TAIWAN_CANONICAL_SAMPLING = 15m`

The canonical Taiwan fixed-grid whole-day realized-variance measurement is the existing XTAI v4 path at a 15-minute sampling interval.

- fixed-grid algorithm: `rv-core-v1+xtai-closing-auction-v4`
- canonical Taiwan sampling: `15m`
- independent benchmark: `tw-rk-parzen-trades-v1`
- RK remains a measurement-identification benchmark and is **not** promoted to the production target.
- no forecast QLIKE or model score entered this decision.

## Why 15m

Task #89 already established that 5m/10m/15m have high rank/log agreement in Taiwan, while their variance levels differ materially. Therefore correlation was not the unresolved identification problem. The unresolved question was which fixed-grid level is most defensible under microstructure noise.

Task #90 selected and parameterized the Parzen realized-kernel benchmark before benchmark-vs-grid results were observed, then ran the frozen comparison over the full preregistered panel:

- 2330 / 2317 / 2454;
- 252 audit sessions per symbol;
- 2025-09-11 through 2026-09-24;
- prior 2025-09-10 session retained only for the first overnight return.

Final panel medians:

| Grid | Geometric level bias vs RK | Mean abs log gap | Pearson log | Spearman |
|---|---:|---:|---:|---:|
| 5m | +34.44% | 0.3511 | 0.9468 | 0.9403 |
| 10m | +17.69% | 0.2724 | 0.9444 | 0.9273 |
| **15m** | **+8.54%** | **0.2660** | 0.9400 | 0.9215 |

Absolute geometric level-bias ordering is unanimous:

- 2330: `15m < 10m < 5m`
- 2317: `15m < 10m < 5m`
- 2454: `15m < 10m < 5m`

Per-symbol geometric bias vs RK:

| Symbol | 5m | 10m | 15m |
|---|---:|---:|---:|
| 2330 | +86.19% | +52.42% | **+35.99%** |
| 2317 | +34.44% | +17.16% | **+7.05%** |
| 2454 | +33.13% | +17.69% | **+8.54%** |

The panel-median mean absolute log gap also favors 15m.

2317 alone has a small mean-absolute-log-gap advantage for 10m over 15m (0.2446 vs 0.2521). That does not overturn the decision because:

1. 15m still has materially smaller 2317 geometric level bias (+7.05% vs +17.16%);
2. 15m has the smallest geometric level bias for every symbol;
3. the original Task #89 blocker was systematic variance-level sensitivity, while high rank/log correlation was already known.

The slightly higher 5m/10m correlations therefore do not resolve the original measurement-identification question and are not used to override the level evidence.

## Empirical execution

Frozen tick collection plan:

- 253 actual XTAI sessions including the prior overnight anchor;
- 3 symbols;
- 759 immutable symbol-day requests;
- 8 deterministic batches;
- no dropped difficult sessions.

Final provider-free empirical workflow:

- run: `36812956091`
- artifact: `11140371482`
- artifact SHA-256:
  `50d54a24cab251c83b11ea8718333128cfdd5d7d0333c750f965db32cb2e7a6f`
- summary SHA-256:
  `101ad519301c989daf8e0c791aab560f60d233ea0e156ed7596e19102b7088d2`
- daily-values SHA-256:
  `606107ad2b27a63df0761df6d88c589f08a2d47a28c593996827c7295898b259`

The final workflow verifies all eight input artifact ZIP digests before use and performs zero provider calls.

## Formula / edge-case validation

The provider-free empirical runner cross-checks the optimized calculation against the frozen production services.

On 2026-04-20 for all three symbols:

- q identity: PASS;
- bandwidth identity: PASS;
- maximum noise-variance difference: approximately `8.47e-22`;
- maximum sparse-RV difference: approximately `2.71e-20`;
- maximum RK difference: approximately `4.91e-17`.

Two real-data contract gaps were fixed tests-first before final execution:

1. equal transaction timestamps are valid and remain in provider order;
2. a constant-price session may legitimately have noise variance = 0, sparse RV = 0, bandwidth = 1 and intraday RK = 0.

The 2454 / 2026-05-04 locked-limit case now replays through the production path without synthetic observations.

## Staleness / previous-tick boundary

The accepted Task #89 v4 fixed-grid panel recorded zero previous-tick samples at 15m for 2330, 2317 and 2454.

The rare previous-tick condition observed in the Taiwan pilot was concentrated in 2454 at 5m, so promotion of 15m does not depend on a stale-price repair path in the accepted three-symbol panel.

## Outlier boundary

15m is not identical to RK and should not be described as latent variance truth.

Largest 15m absolute-log-gap examples include:

- 2330 / 2025-09-15: fixed-grid/RK ratio about 5.24;
- 2317 / 2025-10-09: about 2.62;
- 2454 / 2026-05-07: about 4.41.

The canonical ruling is therefore comparative: among the preregistered 5m/10m/15m fixed-grid candidates, 15m is the most defensible Taiwan choice against the independent noise-robust benchmark. It is not a claim that 15m exactly equals latent integrated variance.

## Boundary

This decision freezes only the Taiwan sampling leg.

It does **not**:

- freeze U.S. measurement;
- complete the cross-market `MEASUREMENT_FROZEN` state;
- change the forecasting model;
- establish Taiwan-specific forecast coefficients;
- authorize 30+30 expansion.

Task #12 / Story #5 remain open until the U.S. provider-backed measurement leg and final cross-market target manifest are complete.
