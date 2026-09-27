# Task #31 — Multiple-window expanding-OOS transfer stability

Status: `TEMPORAL_HETEROGENEITY / MARKET_SPECIFIC_NOT_PROMOTED`

## Question

Story #6 requires complete-date expanding OOS validation in addition to the final chronological holdout.

This task checks whether the H=5 unseen-symbol transfer ordering is stable across four non-overlapping evaluation windows
when every fold is refit using only labels whose five-session targets have fully matured before that fold starts.

Models:

- global pooled Ridge-HAR;
- market-specific Ridge-HAR;
- fixed-alpha global + market-deviation partial pooling.

## Frozen protocol

Inputs are the same seven hash-pinned TradingView Phase 4A exports used in Tasks #25/#27/#29.

Features and response:

```text
xD = log(RV1 / RV22)
xW = log(RV5 / RV22)
z  = log(Y5 / RV22)
```

Folds were fixed before reading fold results:

| Fold | Evaluation window |
|---|---|
| F1 | 2024-12-02 .. 2025-03-31 |
| F2 | 2025-04-01 .. 2025-07-31 |
| F3 | 2025-08-01 .. 2025-12-03 |
| F4 | 2025-12-04 .. data end |

For each fold:

- training expands through all prior eligible history;
- held-out symbol contributes zero fitting rows;
- a training origin is eligible only if its H=5 target is valid;
- the fifth target session must occur strictly before the evaluation start;
- train-only StandardScaler;
- fixed Ridge alpha = 1.0;
- Task #27 partial-pooling design unchanged;
- QLIKE primary;
- paired 20-session moving-block bootstrap, 5,000 replicates, seed `20260926`.

This is a retrospective temporal-stability check, not a newly untouched holdout.

## Overall fold results

Positive `market - global` favors the global model.

| Fold | N dates | Global | Market | Partial | Market-Global | 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| F1 | 85 | 0.357285 | 0.364270 | 0.364273 | +0.006985 | [-0.001228, +0.015575] |
| F2 | 88 | 0.302822 | 0.301417 | 0.301411 | -0.001405 | [-0.005018, +0.004961] |
| F3 | 89 | 0.179314 | 0.182561 | 0.182561 | +0.003247 | [+0.002411, +0.005746] |
| F4 | 202 | 0.165977 | 0.167921 | 0.167922 | +0.001945 | [+0.001024, +0.003258] |

Interpretation:

- F1: global point estimate better, but inconclusive;
- F2: market-specific point estimate better, but inconclusive;
- F3: global clearly better;
- F4: global clearly better.

Therefore the stronger statement that global transfer wins stably in every chronological window is not supported.

## U.S. fold results

| Fold | Market-Global | 95% CI |
|---|---:|---:|
| F1 | +0.008305 | [-0.003864, +0.020910] |
| F2 | +0.000169 | [-0.006575, +0.003099] |
| F3 | +0.005845 | [+0.004794, +0.010226] |
| F4 | +0.001923 | [+0.000750, +0.003434] |

The U.S. panel shows the same timing pattern: early windows are inconclusive; later windows favor global.

## Taiwan fold results

| Fold | Market-Global | 95% CI |
|---|---:|---:|
| F1 | +0.002963 | [-0.003364, +0.003621] |
| F2 | -0.000364 | [-0.004554, +0.020271] |
| F3 | -0.000150 | [-0.001342, +0.000582] |
| F4 | +0.002185 | [-0.001027, +0.005691] |

Taiwan is inconclusive in every fold. No fold provides stable evidence that a Taiwan-specific Ridge-HAR improves unseen
Taiwan securities.

## Partial-pooling behavior

Partial pooling remains nearly coincident with the market-specific model in every fold. Its difference from market-specific
is consistently at the ~1e-6 scale and does not create a materially distinct transfer solution.

## Main finding

The cross-market transfer effect is temporally heterogeneous:

- later windows F3/F4 support global pooling;
- earlier windows do not cleanly separate global and market-specific fits;
- F2 has a small market-specific point advantage, but its interval crosses zero;
- no window produces statistically stable support for market-specific promotion;
- Taiwan-specific improvement is unsupported across all four windows.

This weakens the claim of universal temporal robustness for the pooled global model while leaving the promotion decision
unchanged.

## Ruling

```text
Global shared Ridge-HAR                 KEEP as transfer reference
Global wins every chronological window NO
Temporal stability                     HETEROGENEOUS
Market-specific Ridge-HAR              NOT PROMOTED
Fixed-alpha partial pooling            NOT PROMOTED
Taiwan-specific parameter set          NOT SUPPORTED
Production Frozen v1                   NO CHANGE
```

This result should qualify future summaries of Task #13: the later/final windows favor global, but the broader expanding-OOS
record is not uniformly one-directional.
