# Task #35 — Final HAR / GARCH / EWMA / naive comparator replay

Status: `REPLAYED / OLD_PR21_RULING_REPRODUCED`

## Purpose

The final supplied-panel comparator originally lived only in old Draft PR #21. This task replays it from the seven original
TradingView Phase 4A exports and materializes current-main executable evidence for Story #6.

Compared models:

- unseen-symbol global Ridge-HAR;
- causal Pine Level-HAR;
- causal Pine GARCH;
- Pine HARQ research comparator;
- fixed EWMA;
- naive / recent-variance baseline.

## Frozen protocol

- data start: 2022-07-18;
- global Ridge-HAR training cutoff: 2025-11-25;
- evaluation start: 2025-12-04;
- held-out symbol contributes zero global fitting rows;
- same clean RV validity rules as Task #25;
- H=5 future average whole-day RV target;
- global features:
  - `xD = log(RV1 / RV22)`;
  - `xW = log(RV5 / RV22)`;
  - `z = log(Y5 / RV22)`;
- train-only StandardScaler;
- Ridge alpha fixed at 1.0;
- Pine forecasts are taken from the origin date;
- all models are scored only on common finite/positive evaluation rows;
- QLIKE primary;
- paired 20-session moving-block bootstrap, 5,000 replicates, seed `20260926`.

All seven input SHA-256 values are hard-coded in the runner.

## Alignment oracle

For each Pine comparator, Python computes QLIKE from the origin-date forecast and reconstructed next-five-session actual.
That value is compared with the TradingView-exported matured QLIKE exactly five raw bars later.

All 35 symbol/model checks pass the declared `1e-12` tolerance.

Worst observed maximum absolute difference:

```text
1.7763568394002505e-15
```

This proves the origin forecast / matured-target alignment before accepting comparator scores.

## Per-symbol mean QLIKE

| Held-out | Global | HAR | GARCH | HARQ | EWMA | Naive |
|---|---:|---:|---:|---:|---:|---:|
| GOOGL | 0.243996 | 0.184602 | 0.225043 | 0.185072 | 0.244632 | 0.317753 |
| NVDA | 0.111572 | 0.145288 | 0.134016 | 0.142725 | 0.096118 | 0.155391 |
| QQQ | 0.181825 | 0.142876 | 0.155744 | 0.144833 | 0.176851 | 0.268999 |
| TSM | 0.157013 | 0.126194 | 0.120562 | 0.126817 | 0.134083 | 0.235730 |
| 2330 | 0.142007 | 0.154843 | 0.189887 | 0.154808 | 0.139787 | 0.178993 |
| 2317 | 0.161229 | 0.154588 | 0.149228 | 0.155380 | 0.191205 | 0.159321 |
| 2454 | 0.156929 | 0.146265 | 0.282379 | 0.149711 | 0.154112 | 0.208687 |

These values reproduce the old PR #21 final comparator to reported precision.

## Paired date-level bootstrap

Difference is first model minus second; negative favors the first model.

### Overall

| Comparison | Mean delta | 95% CI | Reading |
|---|---:|---:|---|
| HAR - Global | -0.013993 | [-0.044484, +0.003130] | inconclusive overall |
| GARCH - Global | +0.008681 | [-0.008143, +0.026063] | inconclusive |
| HAR - GARCH | -0.022675 | [-0.053313, -0.006911] | HAR favored |
| HARQ - HAR | +0.000506 | [-0.000383, +0.001776] | no stable HARQ gain |
| EWMA - HAR | +0.012462 | [+0.000081, +0.034094] | HAR favored |
| Naive - HAR | +0.066828 | [+0.037997, +0.111866] | HAR clearly favored |

### U.S.

| Comparison | Mean delta | 95% CI |
|---|---:|---:|
| HAR - Global | -0.023861 | [-0.054961, -0.002899] |
| GARCH - Global | -0.014760 | [-0.038755, +0.006471] |
| HAR - GARCH | -0.009101 | [-0.031495, +0.007185] |
| HARQ - HAR | +0.000121 | [-0.001179, +0.001445] |
| EWMA - HAR | +0.013181 | [-0.003417, +0.035307] |
| Naive - HAR | +0.094728 | [+0.052071, +0.151222] |

On this final window, causal Pine HAR beats the unseen-symbol global Ridge-HAR on the U.S. subset.

### Taiwan

| Comparison | Mean delta | 95% CI |
|---|---:|---:|
| HAR - Global | +0.000876 | [-0.052041, +0.035038] |
| GARCH - Global | +0.041597 | [+0.016893, +0.073767] |
| HAR - GARCH | -0.040721 | [-0.108739, +0.001592] |
| HARQ - HAR | +0.001298 | [-0.000146, +0.003509] |
| EWMA - HAR | +0.010862 | [-0.011497, +0.053459] |
| Naive - HAR | +0.023306 | [-0.020796, +0.085198] |

Taiwan HAR versus global remains inconclusive; GARCH is worse than global on this window.

## Findings

1. The old PR #21 final comparator is reproducible and does not suffer the provenance drift found in the older
   market-specific S2 table.
2. HAR beats GARCH overall with a paired block-bootstrap interval entirely below zero.
3. HARQ does not show stable incremental value over HAR.
4. EWMA is worse than HAR overall, although individual symbols can differ.
5. The naive / recent-variance baseline is clearly worse than HAR overall and on the U.S. subset.
6. The unseen-symbol global Ridge-HAR does not justify replacing the existing causal Pine HAR:
   - U.S. final-window evidence favors HAR;
   - overall and Taiwan comparisons are inconclusive.
7. These findings do not justify ticker-by-ticker model selection.

## Ruling

```text
Causal Pine Level-HAR primary baseline     RETAIN
Per-symbol GARCH                           RETAIN as comparator / not primary
HARQ                                       NOT PROMOTED
EWMA                                       NOT PROMOTED over HAR
Naive / recent-variance baseline           CLEARLY WEAKER overall
Global Ridge-HAR over causal Pine HAR      NOT PROMOTED
Ticker-specific winner switching           NO
Frozen v1 production                       NO CHANGE
```

This task closes the final current-main comparator evidence gap identified by Task #33. Story #6 closure should be decided
only after current-main readback and research-history reconciliation are updated to remove that gap.
