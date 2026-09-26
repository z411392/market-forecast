# Story #5 — Harmonize intraday realized-volatility measurement

## User outcome

在比較 forecast model 前，先取得跨市場可解釋、可重播、沒有用預測分數挑選的 realized-volatility measurement。

## Scope

- provider raw observation provenance
- canonical 1-minute OHLCV
- exchange/session/calendar identity
- deterministic 1m→5m/10m/15m aggregation
- regular-session realized variance
- overnight squared log return
- whole-day realized variance
- realized quarticity / semivariance diagnostics
- measurement audit and freeze

## Primary target after freeze

\[
Y_{t,5}=\frac{1}{5}\sum_{h=1}^{5}V^{WD}_{t+h}
\]

where:

\[
V^{WD}_t=V^{RS}_t+r^2_{ON,t}
\]

H=20 uses the same construction only as confirmatory.

## Acceptance criteria

1. Sampling choice is made from measurement diagnostics, not forecast QLIKE.
2. 5m/10m/15m are aggregated from the same canonical 1m source where feasible.
3. Raw/provider identity, retrieval range, checksum/content identity and transform version are recorded.
4. Missing bars, early closes, auctions and timezone/session boundaries are explicit.
5. U.S. and Taiwan measurement differences are reported separately.
6. Canonical measurement is frozen before Story #6 model comparison.
7. TradingView manual exports may be used as spot-check evidence but not as an automated research data feed.

## Non-goals

- selecting HAR/GARCH/HARQ winner
- market-specific coefficients
- own-stock IV/skew
- B50 changes
