# Task #27 — Ridge-shrunk global + market deviations

Status: `PILOT_RESULT / NOT_PROMOTED`

## Question

Can an explicit market-deviation Ridge-HAR provide a useful middle ground between:

- one fully shared global Ridge-HAR; and
- separate market-specific Ridge-HAR fits?

This is the remaining mandatory Story #6 H=5 model variant after Task #25 repaired the global-vs-market-specific replay path.

## Inputs and frozen protocol

Task #27 reuses the exact hash-pinned seven TradingView Phase 4A exports and Task #25 protocol:

- data start: 2022-07-18;
- training cutoff: 2025-11-25;
- final evaluation start: 2025-12-04;
- H=5 future average whole-day realized variance target;
- held-out security contributes zero fitting rows;
- scale-controlled features:
  - `xD = log(RV1 / RV22)`;
  - `xW = log(RV5 / RV22)`;
  - `z = log(Y5 / RV22)`;
- train-only `StandardScaler`;
- fixed Ridge `alpha=1.0`;
- QLIKE primary;
- paired 20-session moving-block bootstrap, 5,000 replicates, seed `20260926`.

No hyperparameter tuning was performed after observing results.

## Partial-pooling design

Market code:

```text
U.S.    m = -0.5
Taiwan  m = +0.5
```

One pooled Ridge regression is fit on all non-held-out securities with:

```text
shared terms:
    xD
    xW

market-deviation terms:
    m
    m*xD
    m*xW
```

All five predictors are standardized on training data only. L2 regularization is intended to shrink the market-deviation
terms toward zero.

## Results

Negative `partial - global` favors partial pooling. Negative `partial - market` favors partial pooling.

| Held-out | N | Global | Market | Partial | Partial-Global | 95% CI | Partial-Market | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GOOGL | 198 | 0.243996 | 0.245157 | 0.245155 | +0.001159 | [-0.001232, +0.004327] | -0.00000175 | [-0.00000691, +0.00000565] |
| NVDA | 198 | 0.111572 | 0.112936 | 0.112939 | +0.001367 | [+0.000694, +0.002888] | +0.00000297 | [-0.00000072, +0.00000775] |
| QQQ | 198 | 0.181825 | 0.183906 | 0.183908 | +0.002083 | [-0.000237, +0.004117] | +0.00000188 | [-0.00000341, +0.00000596] |
| TSM | 198 | 0.157013 | 0.160128 | 0.160134 | +0.003121 | [+0.000918, +0.006014] | +0.00000556 | [+0.00000077, +0.00001147] |
| 2330 | 191 | 0.142007 | 0.140679 | 0.140680 | -0.001327 | [-0.005468, +0.002769] | +0.00000139 | [-0.00000180, +0.00000456] |
| 2317 | 191 | 0.161229 | 0.168380 | 0.168373 | +0.007144 | [-0.000168, +0.014092] | -0.00000736 | [-0.00001378, -0.00000208] |
| 2454 | 123 | 0.156929 | 0.155485 | 0.155485 | -0.001444 | [-0.002687, -0.000700] | +0.00000014 | [-0.00000685, +0.00000569] |

Date-equal-weight scope summaries:

| Scope | N dates | Global | Market | Partial | Partial-Global | 95% CI | Partial-Market | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Overall | 202 | 0.165960 | 0.167894 | 0.167894 | +0.001934 | [+0.001013, +0.003247] | +0.00000032 | [-0.00000178, +0.00000255] |
| U.S. | 198 | 0.173601 | 0.175532 | 0.175534 | +0.001933 | [+0.000759, +0.003448] | +0.00000217 | [-0.00000030, +0.00000537] |
| Taiwan | 191 | 0.156999 | 0.159131 | 0.159128 | +0.002129 | [-0.001077, +0.005594] | -0.00000258 | [-0.00000528, -0.00000007] |

## Main finding

The preregistered fixed-`alpha=1` candidate does **not** produce a meaningfully distinct middle ground.

Its QLIKE is almost numerically identical to the market-specific model:

```text
overall partial - market = +3.21e-7
95% CI = [-1.78e-6, +2.55e-6]
```

At the same time, relative to the global model:

```text
overall partial - global = +0.001934
95% CI = [+0.001013, +0.003247]
```

Thus the partial candidate inherits the same broad unseen-symbol weakness as the market-specific fit.

This is not evidence that hierarchical/partial pooling can never help. It shows that this fixed-alpha, standardized
market-deviation formulation did not shrink enough to yield a useful compromise and does not justify post-hoc tuning inside
this task.

## Ruling

```text
Global shared Ridge-HAR                    KEEP as stronger transfer reference
Market-specific Ridge-HAR                 NOT PROMOTED
Fixed-alpha market-deviation partial pool NOT PROMOTED
Tune alpha after seeing this result        NO
Production Frozen v1                      NO CHANGE
```

The result completes this bounded H=5 Story #6 model variant. H=20 confirmatory work remains a separate future slice and
was intentionally not mixed into this task.
