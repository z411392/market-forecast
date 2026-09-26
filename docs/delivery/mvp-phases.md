# Delivery Phases

## P0 — Governance & architecture bootstrap

Exit:
- Kaledoxa-derived governance baseline 可追溯
- docs/specs/context/authority 入口成立
- uv monorepo baseline 可驗證

## P1 — Data-source acceptance

Exit:
- U.S. intraday provider go/no-go
- Taiwan intraday provider go/no-go
- timezone/session/corporate-action/provenance contract
- overlap spot-check 對得上 TradingView manual export 的合理區間

## P2 — Measurement harmonization

Exit:
- canonical 1m schema
- deterministic 5/10/15m
- overnight + regular-session + whole-day variance
- measurement audit
- canonical target freeze before forecast model scoring

## P3 — Cross-market transferability

Exit:
- global vs market-specific vs partial-pooling
- per-symbol GARCH/HAR baselines
- unseen-symbol transfer holdout
- final time holdout
- paired date-block bootstrap
- H=5 promotion/stop ruling

## P4 — Pine deployment

Exit:
- frozen manifest
- Pine inference artifact
- Python/Pine golden parity
- prospective post-freeze tracking
