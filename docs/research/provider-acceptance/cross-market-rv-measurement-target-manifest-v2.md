# Cross-market realized-variance measurement and target manifest v2

Status: `MEASUREMENT_FROZEN`

This manifest supersedes v1.

The v1 U.S. 5m decision was invalidated by later Task #100 evidence. Task #106 subsequently re-identified the U.S. sampling rule using a preregistered Bandi–Russell noise-optimal sampling criterion on a non-overlapping 252-session panel, then reproduced the same candidate on the Task #97 panel.

## Canonical market measurements

| Market | Provider | Calendar | Price basis | Sampling | Algorithm |
|---|---|---|---|---:|---|
| U.S. | Alpaca historical SIP | XNAS | split-adjusted | **5m** | `rv-core-v1` |
| Taiwan | Shioaji | XTAI | as-printed | **15m** | `rv-core-v1+xtai-closing-auction-v4` |

No forecast QLIKE or model score entered either sampling decision.

## U.S. authority — Task #106

Primary decision evidence is a non-overlapping panel:
- AAPL / NVDA;
- 252 XNAS sessions;
- 2024-09-19 through 2025-09-22;
- prior 2024-09-18 session retained only as source/session anchor;
- Alpaca SIP split-adjusted 1m bars;
- zero missing grid minutes for both symbols.

The frozen Bandi–Russell-style plug-in criterion selects **5m** for both symbols.

Primary panel:

| Symbol | Median implied optimal interval | Median MSE ratio 5m | 10m | 15m | Session wins 5m / 10m / 15m |
|---|---:|---:|---:|---:|---:|
| AAPL | 6.94m | 1.0008 | 1.0458 | 1.3490 | 125 / 118 / 9 |
| NVDA | 6.66m | 1.0000 | 1.0531 | 1.4339 | 141 / 108 / 3 |

Both the median-MSE criterion and per-session win-count support choose 5m for AAPL and NVDA.

Primary workflow:
- run `36829718016`;
- artifact `11147241072`;
- artifact SHA-256 `2eded721511b2b2700f154e967d754a5c6f2f44eaa1b81ba196f8b9beb53308a`.

The same precommitted formula was then replayed on the later Task #97 panel:
- 252 sessions from 2025-09-24 through 2026-09-24;
- AAPL candidate: 5m;
- NVDA candidate: 5m;
- supporting win counts remain consistent.

Replication workflow:
- run `36830679178`;
- artifact `11146743908`;
- artifact SHA-256 `605bc84b2901de88983e136544bcb28db5b7061905c8d513b63b688cf0e05df1`.

The replication is supporting evidence only; it was not allowed to rescue a failed primary gate.

### Why Tasks #97/#100/#104 are not the final U.S. authority

- Task #97 fixed-grid comparison: `INCONCLUSIVE`.
- Task #100 1m Parzen-RK benchmark: `INCONCLUSIVE`.
- Task #104 showed a material 1m-RK / eligible-trade-RK source-granularity mismatch on one session; it explicitly could not choose sampling.
- Task #102 showed a full AAPL/NVDA × 252 transaction panel would require roughly 60 GiB / 65k paginated requests.
- Task #106 therefore used an independent sampling-theory criterion executable from the accepted complete 1m source.

The partial Task #105 transaction-panel acquisition is not required by the final Task #106 ruling.

## Taiwan authority — Task #90

Taiwan remains frozen at **15m**.

Task #90 compared 5m / 10m / 15m whole-day variance against the independent `tw-rk-parzen-trades-v1` benchmark over 252 sessions for 2330 / 2317 / 2454.

Panel-median bias vs RK:
- 5m: +34.44%;
- 10m: +17.69%;
- 15m: +8.54%.

15m had the smallest absolute level bias for every symbol.

Final workflow:
- run `36812956091`;
- artifact `11140371482`;
- SHA-256 `50d54a24cab251c83b11ea8718333128cfdd5d7d0333c750f965db32cb2e7a6f`.

RK remains a measurement-identification benchmark, not the production target.

## Whole-day measurement invariant

Both markets use:

`regular-session realized variance + squared overnight log return`.

U.S.:
- XNAS regular session;
- split-adjusted Alpaca SIP bars;
- 5m deterministic aggregation;
- previous validated regular close → current regular open overnight return.

Taiwan:
- XTAI v4 exchange-clock semantics;
- 15m fixed-grid sampling;
- factual opening observation;
- previous-tick provenance only when required;
- factual 13:30 closing-auction observation;
- previous validated 13:30 close → current factual opening observation.

## Frozen forecasting target

Primary:
**H=5 future average whole-day variance**.

Confirmatory:
**H=20 future average whole-day variance**.

Identity:
- `target_version = whole_day_variance_v1`;
- builder: `build_future_variance_targets`;
- origin-day measurement excluded;
- target begins at the next validated local session;
- missing expected sessions fail closed;
- output stays on variance scale.

For origin session `t`:

`Y[t,H] = (1/H) * sum_{j=1..H} V_WD[t+j]`.

## Governance boundary

This v2 manifest is the measurement authority for subsequent model comparison.

The following remain downstream:
- global vs market-specific vs partial-pooling dynamics;
- HAR/GARCH/Ridge-HAR model comparison;
- QLIKE evaluation;
- broad 30+30 confirmatory work;
- frozen Pine inference parity.

Those stages may evaluate models against this target, but may not re-select the measurement sampling interval from forecast scores.

The v1 manifest is superseded and must not be used as modeling authority.
