# Task #98 — U.S. canonical measurement decision

Status: `ACCEPTED / FINAL`

## Decision

`US_CANONICAL_SAMPLING = 5m`

Canonical U.S. measurement:
- provider: Alpaca historical SIP;
- price basis: split-adjusted;
- algorithm: `rv-core-v1`;
- whole-day variance = regular-session realized variance + squared overnight return;
- sampling interval: 5 minutes.

No forecast QLIKE or model score entered this decision.

## Why 5m

The U.S. practical reference was preregistered at 5m before the provider-backed panel was observed.

Before running the full audit, Task #98 froze an explicit level-sensitivity gate:

- AAPL absolute geometric 5m-vs-10m bias < 10%;
- AAPL absolute geometric 5m-vs-15m bias < 10%;
- NVDA absolute geometric 5m-vs-10m bias < 10%;
- NVDA absolute geometric 5m-vs-15m bias < 10%;
- no provider/session/price-basis pathology.

If any comparison had reached double-digit level sensitivity, the U.S. leg would have remained inconclusive and required an independent noise-robust benchmark rather than switching post hoc to 10m/15m.

The full panel passes that gate.

## Empirical panel

Symbols:
- AAPL
- NVDA

Window:
- prior overnight anchor: 2025-09-23;
- 252 audit sessions: 2025-09-24 through 2026-09-24;
- calendar: XNAS.

Source:
- Alpaca SIP 1-minute historical bars;
- split-adjusted;
- exact regular-session bounds;
- no synthetic/forward-filled minute bars.

Every symbol:
- 253/253 accepted source sessions;
- 252/252 measurement-audit rows.

### Per-symbol metrics

| Symbol | Geo bias 5m/10m | Geo bias 5m/15m | Mean abs log gap 5m/10m | Mean abs log gap 5m/15m |
|---|---:|---:|---:|---:|
| AAPL | +3.72% | +5.36% | 0.1743 | 0.2372 |
| NVDA | +2.53% | +5.42% | 0.1412 | 0.2103 |

Correlations remain high:

| Symbol | Pearson log 5m/10m | Pearson log 5m/15m | Spearman 5m/10m | Spearman 5m/15m |
|---|---:|---:|---:|---:|
| AAPL | 0.9498 | 0.9177 | 0.9391 | 0.9011 |
| NVDA | 0.9665 | 0.9255 | 0.9605 | 0.9326 |

Panel medians:
- geometric 5m-vs-10m bias: +3.12%;
- geometric 5m-vs-15m bias: +5.39%;
- mean abs log gap 5m/10m: 0.1578;
- mean abs log gap 5m/15m: 0.2237.

## Evidence

Workflow:
- run `36823619958`: PASS.

Artifact:
- ID `11145015407`;
- SHA-256 `89c7c72af09998ea175e3bdd4241207618ea811e311c884b2dcc44fdb732797e`;
- summary SHA-256 `a6234bd7cbca77aff7a13d0f7fd25ce94445b73f376fc9e00e73fa3b7880d560`.

The artifact contains immutable per-session Alpaca request/raw-response evidence for all 506 symbol-session captures.

## Comparison with Taiwan

Taiwan and U.S. are intentionally allowed to have different canonical sampling rules:

- U.S.: 5m
- Taiwan: 15m

Taiwan required an independent realized-kernel benchmark because its fixed-grid panel showed systematic double-digit level sensitivity.

The U.S. panel does not cross the preregistered double-digit sensitivity gate, so the existing 5m reference is retained.

## Boundary

This completes the U.S. sampling leg only.

The final Task #12 cross-market freeze still requires a durable measurement/target manifest that records:
- U.S. 5m / split-adjusted / `rv-core-v1`;
- Taiwan 15m / XTAI v4 whole-day semantics;
- H=5 primary future-average variance target;
- H=20 confirmatory target;
- target version `whole_day_variance_v1`.
