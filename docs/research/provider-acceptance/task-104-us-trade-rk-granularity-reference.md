# Task #104 — U.S. 1m-RK vs eligible-trade RK granularity

Status: `ACCEPTED / SOURCE GRANULARITY MISMATCH`

Provider calls: `0`.

Workflow:
- run `36828345487`;
- artifact `11146116203`;
- SHA-256 `9bcb1c7b0ae2924833f97617e8b97259988e01437caebaa02e55dcaad2a0bb38`.

Frozen diagnostic boundary:
`abs(log(RK_1m / RK_trade)) <= log(1.10)` for both symbols would mean no gross source-granularity mismatch.

Results:

| Symbol | 1m-RK / trade-RK | abs log ratio | Boundary |
|---|---:|---:|---|
| AAPL | 0.8626 | 0.1478 | FAIL |
| NVDA | 0.8590 | 0.1519 | FAIL |

Ruling:
`MATERIAL_SOURCE_GRANULARITY_MISMATCH`.

The accepted 1m-bar RK is about 14% below eligible-transaction RK on this session for both symbols.

Fixed-grid / trade-RK ratios are not a sampling decision:
- AAPL: 5m 0.7743, 10m 0.6811, 15m 1.0556;
- NVDA: 5m 0.9848, 10m 0.9104, 15m 0.8232.

Thus the closest fixed-grid interval differs by symbol on the diagnostic session (AAPL 15m, NVDA 5m). No canonical sampling interval is selected.

The result establishes that 1m source granularity is a material measurement dimension for the U.S. RK benchmark, while Task #102 establishes that a brute-force 2x252 raw trade panel would be about 60 GiB / 65,780 page requests.
