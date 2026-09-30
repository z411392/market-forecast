# Task #90 S4g — 164-session interim RK comparison

Status: `INTERIM / NOT FINAL FREEZE`

The first five frozen tick batches are complete, providing one prior overnight anchor plus 164 audit sessions for each of 2330, 2317 and 2454.

## Core result

Against the frozen `tw-rk-parzen-trades-v1` benchmark, fixed-grid level bias is ordered consistently across all three symbols:

`15m < 10m < 5m`.

Panel medians:

| Grid | Geometric bias vs RK | Mean abs log gap | Pearson log | Spearman |
|---|---:|---:|---:|---:|
| 5m | +52.45% | 0.4599 | 0.9460 | 0.9235 |
| 10m | +27.06% | 0.3097 | 0.9445 | 0.9216 |
| 15m | +15.09% | 0.2829 | 0.9363 | 0.9163 |

15m has the smallest geometric level bias for every symbol. On mean absolute log gap, 15m is best for 2330 and 2454; 10m is slightly better for 2317. The panel median still favors 15m.

## Reproducibility checks

Fixed-grid reconstruction matches durable Task #89 rows to floating-point precision:
- 2330 / 2025-12-05: maximum absolute variance difference below 1.8e-17;
- 2454 / 2025-11-11: maximum absolute variance difference below 9.2e-18.

The optimized provider-free calculation was also checked against the already-frozen sparse-RV / Parzen-RK formula on one actual session per symbol; differences are around 1e-17 or smaller.

## Boundary

This does not freeze Taiwan canonical measurement.

The preregistered final gate remains 252 audit sessions. Current complete tick evidence covers 164.

Batch 6 attempted under the Product-Owner-authorized 100 MiB remaining-traffic reserve and stopped before any new tick request:
- provider remaining: 104,771,185 bytes;
- reserve: 104,857,600 bytes;
- acquired: 0;
- deferred: 99.

The only remaining Taiwan core blocker is collection of frozen batches 6-8 after provider traffic becomes available again. No new model or measurement experiment is introduced.
