# Cross-market realized-variance measurement and target manifest v1

Status: `MEASUREMENT_FROZEN`

## Canonical market measurements

| Market | Provider | Calendar | Price basis | Sampling | Algorithm |
|---|---|---|---|---:|---|
| U.S. | Alpaca historical SIP | XNAS | split-adjusted | **5m** | `rv-core-v1` |
| Taiwan | Shioaji | XTAI | as-printed | **15m** | `rv-core-v1+xtai-closing-auction-v4` |

These market-specific sampling rules were selected from provider-backed measurement evidence before forecast-model comparison.

### U.S.

Task #98 froze 5m after the preregistered double-digit level-sensitivity gate passed on AAPL/NVDA over 252 sessions.

Panel-median geometric level bias:
- 5m vs 10m: +3.12%;
- 5m vs 15m: +5.39%.

Both symbols remained below the preregistered 10% absolute-bias gate.

### Taiwan

Task #90 froze 15m after comparing 5m/10m/15m against the independent `tw-rk-parzen-trades-v1` benchmark over 252 sessions for 2330/2317/2454.

Panel-median level bias vs RK:
- 5m: +34.44%;
- 10m: +17.69%;
- 15m: +8.54%.

RK remains an identification benchmark, not the production target.

## Whole-day measurement invariant

Both markets use whole-day variance:

`regular-session realized variance + overnight squared log return`.

Market-specific session semantics remain explicit.

U.S.:
- exchange-calendar regular session;
- split-adjusted bars;
- previous validated regular close -> current regular open for overnight return.

Taiwan:
- XTAI v4 exchange-clock sampling;
- factual opening observation;
- explicit previous-tick provenance only when needed;
- 13:30 closing-auction observation;
- previous validated 13:30 close -> current factual opening observation.

## Frozen forecasting target

Primary target:
- **H=5 future average whole-day variance**.

Confirmatory target:
- **H=20 future average whole-day variance**.

Target identity:
- `target_version = whole_day_variance_v1`;
- builder: `build_future_variance_targets`;
- origin session measurement is not included;
- first target session is the next validated local exchange session;
- missing expected sessions fail closed rather than compressing the horizon;
- target stays on variance scale, not volatility scale.

For origin session `t`:

[
Y_{t,H} = \frac{1}{H}\sum_{j=1}^{H} RV^{canonical}_{t+j}
]

where each market uses its own frozen canonical intraday sampling rule.

## Governance boundary

Measurement selection is complete before forecast-model comparison.

The following remain outside this manifest:
- global vs market-specific vs partial-pooling parameter selection;
- HAR/GARCH/Ridge-HAR model ranking;
- QLIKE comparison;
- later 30+30 broad-universe confirmation;
- Pine deployment/inference parity.

Those stages must consume this frozen measurement identity rather than re-select sampling frequency from model scores.

## Durable evidence

Taiwan:
- Task #90 final decision;
- final 252-session RK workflow `36812956091`;
- artifact `11140371482`.

U.S.:
- Task #95 Alpaca SIP source acceptance;
- Task #98 final 252-session audit workflow `36823619958`;
- artifact `11145015407`.

Machine-readable authority:
`docs/research/provider-acceptance/cross-market-rv-measurement-target-manifest-v1.json`.
