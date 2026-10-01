# Task #102 — Alpaca SIP trade-tick feasibility

Status: `ACCEPTED / FULL PANEL NOT AUTHORIZED`

No realized-kernel benchmark value was computed in this task.

## Live sample

Exact sample:
- AAPL / 2026-09-24 regular session;
- NVDA / 2026-09-24 regular session;
- Alpaca historical SIP trades;
- pagination limit 10,000;
- all pages followed to `next_page_token = null`.

Workflow:
- run `36826142897`;
- artifact `11145730777`;
- SHA-256 `a34d32b443d82df4de548a2eca834b438cff4aa2dba03c0107a63c8a76981d3f`.

Observed:

| Symbol | Pages | Trades | Raw bytes | Bytes/trade |
|---|---:|---:|---:|---:|
| AAPL | 51 | 506,108 | 49,253,464 | 97.32 |
| NVDA | 209 | 2,087,331 | 205,910,255 | 98.65 |
| Total | 260 | 2,593,439 | 255,163,719 | — |

Both streams are non-decreasing in nanosecond timestamp order and span the exact regular session.

## Full-panel planning

Linear projection to the existing 506 symbol-days:

- about 65,780 page requests;
- about 64.56 billion raw bytes;
- about 61,566 MiB / 60.1 GiB raw JSON.

This is technically retrievable but is not a bounded research capture under the current Task #12 program.

## Trade-condition finding

The raw transaction stream is not equivalent to the minute-bar price process.

Observed odd-lot condition `I`:
- AAPL: ~73.18% of trades;
- NVDA: ~90.59% of trades.

Alpaca's published SIP bar-update rules state that condition `I` does not update minute-bar open/close/high/low prices. Other observed conditions such as `4`, `7`, `V`, `W`, `Z`, `P`, `Q` also have condition-specific price-update rules.

Therefore a transaction-time RK must not blindly consume all historical trades if it is intended to be measurement-compatible with the accepted Alpaca SIP bar source. A deterministic price-eligibility rule must be frozen first.

## Ruling

`ALPACA_SIP_TRADES = TECHNICALLY_FEASIBLE`

`FULL_2x252_RAW_TICK_PANEL = NOT_AUTHORIZED`

`TRANSACTION_RK_INPUT_RULE = NOT_YET_FROZEN`

Next core step, if transaction-RK is pursued, is source-semantic only:
- freeze a deterministic SIP trade-price eligibility rule from Alpaca's published minute-bar update table;
- validate that rule on a small already-captured sample;
- only then decide whether a bounded transaction-RK comparison is worth additional collection.

No benchmark family switch, forecast score, or full-panel acquisition is introduced here.
