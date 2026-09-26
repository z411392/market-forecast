# Task #23 — Matched Level-HAR vs Log-HAR

Status: `PILOT_RESULT / KEEP_LEVEL_HAR`

## Question

The historical v1.5 research note described Log-HAR, while the later Phase 4A Pine research and Frozen v1 deployment use
Level-HAR. On the supplied cross-market panel, does the log transform produce lower H=5 QLIKE under an otherwise matched
causal protocol?

## Inputs

Original Phase 4A TradingView exports supplied by the user:

| Symbol | Market | SHA-256 |
|---|---|---|
| GOOGL | U.S. | `2c09055672391ba0724d0918ddc86f621254154be20ef457c28b7a62f6ff34ba` |
| NVDA | U.S. | `99323dc9644f2a5955f1b6119b2d75c7c6dcce8c7b2938be81c610871c5dc54c` |
| QQQ | U.S. | `18fd0c5050c348516f616da8abcc764707f4aa669b7ba022a12ce1362954243e` |
| TSM | U.S. | `f66835e9328fbe261472a8a693efb898ee144b1d90cfb38c0732037cc58abec4` |
| 2330 | Taiwan | `e26c29335402363c4a1b8aae35bb26e63bb1577bed74173f5b914f7258ca3d47` |
| 2317 | Taiwan | `98a0b83bb2ced641603a6b248853a0fc288a80d06cae4f8212ab813d54866c5c` |
| 2454 | Taiwan | `791626c2890e5aad95d19abc4e4c84586686394b9f81b4fa2d53363465792847` |

Raw exports are not committed.

## Frozen protocol

Both models use the same Phase 4A whole-day RV stream and the same causal 504-matured-row rolling OLS fit.
At bar `t`, the newly matured label belongs to origin `t-5`.

Level-HAR:

```text
Y5_t = beta0 + betaD * RV1_t + betaW * RV5_t + betaM * RV22_t
```

Log-HAR, using the historical specification exactly:

```text
log(Y5_t) = beta0 + betaD * log(RV1_t) + betaW * log(RV5_t) + betaM * log(RV22_t)
forecast_t = exp(predicted_log_Y5_t)
```

No smearing or other post-hoc retransformation correction is applied.

Scoring starts on 2025-12-04. Scoring origins require the Task #13 clean measurement rule: all 22 trailing and all next 5
RV observations must pass the market-specific intrabar-count validity rule. Model fitting itself preserves the unmodified
Phase 4A RV stream for exact parity with the exported Level-HAR implementation.

Primary metric is QLIKE. `Log-HAR - Level-HAR` is reported, so a negative value favors Log-HAR. Uncertainty uses a paired
20-session moving-block bootstrap with 5,000 replicates and deterministic seed `20260926`.

## Phase 4A Level-HAR reconstruction parity

Python reconstruction matches the exported `P4_FORECAST_HAR_LEVEL_VAR5` path to floating-point precision:

| Symbol | Finite overlap | Maximum absolute difference |
|---|---:|---:|
| GOOGL | 329 | 2.66e-18 |
| NVDA | 255 | 3.47e-18 |
| QQQ | 255 | 1.41e-18 |
| TSM | 255 | 2.82e-18 |
| 2330 | 855 | 2.60e-17 |
| 2317 | 855 | 1.13e-16 |
| 2454 | 856 | 4.73e-17 |

## Per-symbol final-window QLIKE

| Symbol | N | Level-HAR | Log-HAR | Log - Level | 95% block-bootstrap CI |
|---|---:|---:|---:|---:|---:|
| GOOGL | 198 | 0.184602 | 0.209069 | +0.024467 | [-0.023945, +0.086230] |
| NVDA | 198 | 0.145288 | 0.092702 | -0.052586 | [-0.087014, -0.011289] |
| QQQ | 198 | 0.142876 | 0.167969 | +0.025093 | [-0.015056, +0.085336] |
| TSM | 198 | 0.126194 | 0.141894 | +0.015700 | [-0.002628, +0.049563] |
| 2330 | 191 | 0.154843 | 0.137416 | -0.017427 | [-0.052789, +0.028496] |
| 2317 | 191 | 0.154588 | 0.144073 | -0.010515 | [-0.038523, +0.033154] |
| 2454 | 123 | 0.146265 | 0.165731 | +0.019466 | [+0.001290, +0.046545] |

Only NVDA has an interval fully favoring Log-HAR; only 2454 has an interval fully favoring Level-HAR. The remaining five
symbols do not separate the transforms at the 95% block-bootstrap level.

## Equal-weight date summaries

| Scope | N dates | Level-HAR | Log-HAR | Log - Level | 95% block-bootstrap CI |
|---|---:|---:|---:|---:|---:|
| Overall | 202 | 0.151967 | 0.151992 | +0.000025 | [-0.018214, +0.029104] |
| U.S. | 198 | 0.149740 | 0.152909 | +0.003169 | [-0.016697, +0.036269] |
| Taiwan | 191 | 0.157876 | 0.150846 | -0.007030 | [-0.030874, +0.027519] |

## Ruling

The matched pilot does not support reopening Frozen v1 to change Level-HAR into Log-HAR.

- Overall QLIKE is effectively identical.
- U.S. and Taiwan point estimates lean in opposite directions, and both confidence intervals cross zero.
- Symbol-level directions are heterogeneous: NVDA supports Log-HAR while 2454 supports Level-HAR.
- Selecting transforms ticker by ticker would repeat the model-selection-overfitting problem already rejected in the
  historical research record.

Therefore:

```text
Frozen v1 Level-HAR            KEEP
Switch production to Log-HAR   NO
Ticker-specific transform rule NO
Historical Log-HAR hypothesis  TESTED, NOT PROMOTED
```

This result resolves the documentation/specification ambiguity for the supplied 4-U.S. + 3-Taiwan pilot. It does not claim
that Level-HAR is universally superior; the evidence says the transform choice is not stably separable on this panel.
