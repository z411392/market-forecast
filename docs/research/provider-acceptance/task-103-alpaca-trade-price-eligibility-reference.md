# Task #103 — Alpaca SIP trade price eligibility

Status: `ACCEPTED`

The transaction-price eligibility rule required for a future U.S. trade-based realized-kernel benchmark is now frozen.

Rule:
- Nasdaq tape C;
- minute-bar open/close price semantics;
- strictest condition wins;
- eligible codes: `@ A B D F K L O T X Y 5 6`;
- ineligible codes: `C G H I M N P Q R U V W Z 4 7 9`;
- unknown conditions fail closed.

Provider-free replay:
- run `36827499222`;
- artifact `11145463492`;
- artifact SHA-256 `78ea597e5c364db51c9d9f8293ebbff5d60317803dc9f0a08777251249be54df`.

2026-09-24 exact replay:

| Symbol | Raw trades | Eligible trades | Eligible share | Minutes | OHLC mismatches |
|---|---:|---:|---:|---:|---:|
| AAPL | 506,108 | 131,127 | 25.91% | 390 | 0 |
| NVDA | 2,087,331 | 193,239 | 9.26% | 390 | 0 |

For both symbols, reconstructed minute OHLC equals the accepted Alpaca SIP bar artifact exactly; maximum absolute OHLC difference is 0.

No provider call and no RK value was produced in this Task.
