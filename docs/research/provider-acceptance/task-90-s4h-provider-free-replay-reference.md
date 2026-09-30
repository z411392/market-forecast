# Task #90 S4h — Provider-free empirical replay

Status: `ACCEPTED / FINAL DATA PENDING`

The Taiwan realized-kernel empirical comparison is now replayable from immutable GitHub Actions artifacts without any Shioaji call.

## What is proven

- batch 1–5 artifact ZIP SHA-256 values are verified before use;
- 164 audit sessions per symbol reproduce the durable S4g interim metrics within `1e-10`;
- optimized empirical calculation is cross-checked against the frozen production formula on 2026-04-20 for all three symbols;
- timestamp ties are supported consistently with the canonical provider-order transaction contract;
- the real 2454 / 2026-05-04 zero-intraday-variance session is replayable with:
  - noise variance = 0;
  - sparse RV = 0;
  - bandwidth = 1;
  - intraday RK = 0;
  - whole-day variance supplied only by overnight variance.

Workflow:
- run `36719846796`;
- artifact `11097866806`;
- artifact SHA-256 `0010115e8017bc0dacbeeac627e3284c156c61ab0861e37d31d3cfd9a86a07d3`.

## Current 164-session measurement result

| Grid | Panel median geometric bias vs RK | Panel median mean abs log gap |
|---|---:|---:|
| 5m | +52.45% | 0.4599 |
| 10m | +27.06% | 0.3097 |
| 15m | +15.09% | 0.2829 |

Geometric level bias ordering is `15m < 10m < 5m` for 2330, 2317 and 2454.

This remains interim because the preregistered final gate is 252 audit sessions.

## Final execution path

No new research code is required.

After provider traffic becomes available:
1. acquire frozen batches 6–8;
2. append their artifact IDs/digests to `task-90-s4h-empirical-input.json`;
3. set expected session count to 253 and audit count to 252;
4. rerun the same S4h provider-free workflow;
5. issue the Taiwan canonical-measurement verdict from that full-panel output.
