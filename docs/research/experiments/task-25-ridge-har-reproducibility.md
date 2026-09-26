# Task #25 — Ridge-HAR transfer reproducibility repair

Status: `REPRODUCIBILITY_REPAIRED / DECISION_UNCHANGED`

## Purpose

Task #13 recorded a first-pass global pooled Ridge-HAR vs market-specific Ridge-HAR unseen-symbol experiment. A later
runner committed under Task #13 only materialized the global/Pine-comparator stage, so the original market-specific table
could not be regenerated directly from repository code.

During Task #14 review, a fresh recomputation from the original seven TradingView exports produced slightly different point
estimates while preserving the same product decision. This task makes that exact protocol replayable and records the
current reproducible result.

## Inputs

| Symbol | Market | SHA-256 |
|---|---|---|
| GOOGL | U.S. | `2c09055672391ba0724d0918ddc86f621254154be20ef457c28b7a62f6ff34ba` |
| NVDA | U.S. | `99323dc9644f2a5955f1b6119b2d75c7c6dcce8c7b2938be81c610871c5dc54c` |
| QQQ | U.S. | `18fd0c5050c348516f616da8abcc764707f4aa669b7ba022a12ce1362954243e` |
| TSM | U.S. | `f66835e9328fbe261472a8a693efb898ee144b1d90cfb38c0732037cc58abec4` |
| 2330 | Taiwan | `e26c29335402363c4a1b8aae35bb26e63bb1577bed74173f5b914f7258ca3d47` |
| 2317 | Taiwan | `98a0b83bb2ced641603a6b248853a0fc288a80d06cae4f8212ab813d54866c5c` |
| 2454 | Taiwan | `791626c2890e5aad95d19abc4e4c84586686394b9f81b4fa2d53363465792847` |

Raw user exports are not committed.

## Frozen protocol

- data start: 2022-07-18;
- training cutoff: 2025-11-25;
- evaluation start: 2025-12-04;
- H=5 future average whole-day RV target;
- U.S. RV day is valid for 78 regular-session or 42 early-close 5m bars;
- Taiwan RV day is valid for 53 5m bars;
- no interpolation or forward fill;
- held-out security contributes zero fitting rows;
- global model trains on all other symbols;
- market model trains only on other symbols from the held-out security's market;
- scale-controlled features:
  - `xD = log(RV1 / RV22)`;
  - `xW = log(RV5 / RV22)`;
  - `z = log(Y5 / RV22)`;
- train-only `StandardScaler`;
- fixed Ridge `alpha=1.0`;
- reconstructed forecast = `RV22 * exp(z_hat)`;
- primary loss = QLIKE;
- delta = market-specific QLIKE minus global QLIKE;
- paired moving-block bootstrap: 20-session blocks, 5,000 replicates, seed `20260926`.

## Current reproducible result

| Held-out | Market | N | Global QLIKE | Market QLIKE | Market - Global | 95% CI |
|---|---|---:|---:|---:|---:|---:|
| GOOGL | U.S. | 198 | 0.243996 | 0.245157 | +0.001161 | [-0.001228, +0.004321] |
| NVDA | U.S. | 198 | 0.111572 | 0.112936 | +0.001364 | [+0.000692, +0.002881] |
| QQQ | U.S. | 198 | 0.181825 | 0.183906 | +0.002081 | [-0.000236, +0.004116] |
| TSM | U.S. | 198 | 0.157013 | 0.160128 | +0.003115 | [+0.000916, +0.006006] |
| 2330 | Taiwan | 191 | 0.142007 | 0.140679 | -0.001329 | [-0.005470, +0.002765] |
| 2317 | Taiwan | 191 | 0.161229 | 0.168380 | +0.007151 | [-0.000165, +0.014103] |
| 2454 | Taiwan | 123 | 0.156929 | 0.155485 | -0.001444 | [-0.002688, -0.000700] |

Date-equal-weight summaries:

| Scope | N dates | Global QLIKE | Market QLIKE | Market - Global | 95% CI |
|---|---:|---:|---:|---:|---:|
| Overall | 202 | 0.165960 | 0.167894 | +0.001934 | [+0.001012, +0.003246] |
| U.S. | 198 | 0.173601 | 0.175532 | +0.001930 | [+0.000758, +0.003444] |
| Taiwan | 191 | 0.156999 | 0.159131 | +0.002131 | [-0.001076, +0.005598] |

Positive delta favors the global model.

## Difference from the older Task #13 S2 table

The older S2 artifact reported slightly different point estimates, for example overall `+0.002047` instead of the current
reproducible `+0.001934`.

The repository did not contain a runner for the market-specific branch at the time, so the older numbers cannot be traced to
an exact committed implementation. They remain historical evidence, but this Task #25 result is the replayable current
reference for the frozen S2 protocol.

The difference is not decision-relevant:

- overall and U.S. intervals remain entirely positive, favoring the global model;
- Taiwan remains inconclusive;
- individual Taiwan symbols still disagree in direction;
- there is still no stable evidence supporting a Taiwan-specific parameter set.

## Ruling

```text
Market-specific Ridge-HAR promotion   NO
Global-vs-market decision             UNCHANGED
Production Frozen v1                  NO CHANGE
Old S2 table                          HISTORICAL / SUPERSEDED FOR REPLAY
Task #25 result                       CURRENT REPRODUCIBLE REFERENCE
```

This task repairs provenance and replayability only. It does not promote the global Ridge-HAR as the production model;
Task #13's later matched comparison against the causal Pine HAR still governs that separate question.
