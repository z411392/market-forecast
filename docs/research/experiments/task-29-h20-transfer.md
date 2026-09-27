# Task #29 — H=20 confirmatory cross-market transfer

Status: `CONFIRMATORY_RESULT / H5_RULING_NOT_CONTRADICTED`

## Question

Story #6 defines H=5 as primary and H=20 as confirmatory. This task asks whether the longer H=20 target materially
contradicts the H=5 unseen-symbol transfer result for:

- global pooled Ridge-HAR;
- market-specific Ridge-HAR;
- fixed-alpha global + market-deviation partial pooling.

## Inputs and frozen protocol

The task reuses the exact seven hash-pinned TradingView Phase 4A exports used in Tasks #25/#27.

Target:

```text
Y20_t = mean(RV[t+1] ... RV[t+20])
```

Scale-controlled response and features:

```text
xD = log(RV1 / RV22)
xW = log(RV5 / RV22)
z  = log(Y20 / RV22)
```

Validation:

- data start: 2022-07-18;
- final evaluation starts: 2025-12-04;
- held-out security contributes zero fitting rows;
- a training origin is eligible only if all next 20 RV observations are valid;
- the 20th target session must occur strictly before 2025-12-04;
- this maturity-date rule enforces the H=20 purge in each symbol's own local-session sequence;
- train-only StandardScaler;
- fixed Ridge alpha = 1.0;
- partial-pooling design exactly matches Task #27;
- QLIKE primary;
- paired 20-session moving-block bootstrap, 5,000 replicates, seed 20260926.

No H=5 or alpha tuning was performed.

## Results

Positive `market - global` or `partial - global` favors the global model.

| Held-out | N | Global | Market | Partial | Market-Global | 95% CI | Partial-Global | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GOOGL | 183 | 0.139740 | 0.141929 | 0.141932 | +0.002189 | [-0.001494, +0.009769] | +0.002192 | [-0.001494, +0.009781] |
| NVDA | 183 | 0.061182 | 0.062426 | 0.062427 | +0.001243 | [-0.000911, +0.002991] | +0.001245 | [-0.000910, +0.002994] |
| QQQ | 183 | 0.158859 | 0.159074 | 0.159077 | +0.000215 | [-0.005138, +0.004844] | +0.000217 | [-0.005138, +0.004849] |
| TSM | 183 | 0.084411 | 0.087699 | 0.087703 | +0.003288 | [+0.000918, +0.007300] | +0.003292 | [+0.000920, +0.007309] |
| 2330 | 176 | 0.086823 | 0.085312 | 0.085312 | -0.001511 | [-0.007607, +0.000899] | -0.001511 | [-0.007605, +0.000898] |
| 2317 | 176 | 0.158295 | 0.167739 | 0.167734 | +0.009445 | [+0.001575, +0.014672] | +0.009439 | [+0.001573, +0.014661] |
| 2454 | 81 | 0.096624 | 0.098718 | 0.098716 | +0.002094 | [-0.005666, +0.009705] | +0.002092 | [-0.005663, +0.009698] |

Equal-weight date summaries:

| Scope | N dates | Global | Market | Partial | Market-Global | 95% CI | Partial-Global | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Overall | 186 | 0.112958 | 0.115278 | 0.115279 | +0.002320 | [+0.000282, +0.003546] | +0.002321 | [+0.000283, +0.003547] |
| U.S. | 183 | 0.111048 | 0.112782 | 0.112785 | +0.001734 | [+0.000044, +0.004439] | +0.001737 | [+0.000046, +0.004444] |
| Taiwan | 176 | 0.118917 | 0.122134 | 0.122132 | +0.003217 | [-0.002761, +0.005241] | +0.003214 | [-0.002761, +0.005237] |

Partial pooling again remains effectively coincident with the market-specific model:

```text
overall partial - market = +9.19e-7
95% CI = [-8.00e-8, +3.33e-6]
```

## Interpretation

H=20 is confirmatory and points in the same direction as the H=5 primary result:

- overall unseen-symbol transfer favors the global shared Ridge-HAR;
- U.S. transfer also favors global, although the lower CI boundary is close to zero;
- Taiwan remains inconclusive rather than supporting a Taiwan-specific model;
- TSM and 2317 materially favor global at H=20;
- per-symbol directions are still heterogeneous, so ticker-specific model selection remains unsupported;
- fixed-alpha partial pooling still does not create a useful intermediate structure.

The confirmatory horizon therefore does not expose a material contradiction that would reopen the H=5 promotion decision.

## Ruling

```text
H=5 primary transfer ruling             CONFIRMED, NOT REOPENED
Global shared Ridge-HAR                 KEEP as transfer reference
Market-specific Ridge-HAR               NOT PROMOTED
Fixed-alpha market-deviation partial    NOT PROMOTED
Taiwan-specific parameter set           NOT SUPPORTED
Production Frozen v1                    NO CHANGE
```

This task completes the bounded H=20 confirmatory transfer slice. It does not claim a universal cross-market model beyond
the supplied 4-U.S. + 3-Taiwan pilot.
