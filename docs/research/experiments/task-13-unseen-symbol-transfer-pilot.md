# Task #13 — Unseen-Symbol Cross-Market Ridge-HAR Pilot

Status: PILOT_RESULT / NOT_PRODUCTION_PROMOTION

## Question

After using the same realized-variance measurement contract and controlling local variance scale, does market identity improve
H=5 volatility forecasts on securities that were not used to fit the model?

## Inputs

TradingView Phase 4A chart-data exports supplied by the user.

| Symbol | Market | SHA-256 |
|---|---|---|
| GOOGL | US | `2c09055672391ba0724d0918ddc86f621254154be20ef457c28b7a62f6ff34ba` |
| NVDA | US | `99323dc9644f2a5955f1b6119b2d75c7c6dcce8c7b2938be81c610871c5dc54c` |
| QQQ | US | `18fd0c5050c348516f616da8abcc764707f4aa669b7ba022a12ce1362954243e` |
| TSM | US | `f66835e9328fbe261472a8a693efb898ee144b1d90cfb38c0732037cc58abec4` |
| 2330 | Taiwan | `e26c29335402363c4a1b8aae35bb26e63bb1577bed74173f5b914f7258ca3d47` |
| 2317 | Taiwan | `98a0b83bb2ced641603a6b248853a0fc288a80d06cae4f8212ab813d54866c5c` |
| 2454 | Taiwan | `791626c2890e5aad95d19abc4e4c84586686394b9f81b4fa2d53363465792847` |

Raw user CSVs are not committed.

## Frozen first-pass protocol

- Data start: 2022-07-18.
- U.S. daily RV valid only for 78 regular-session 5m bars or 42 early-close bars.
- Taiwan daily RV valid only for 53 5m bars.
- No forward fill or interpolation.
- An origin is eligible only when all 22 trailing RV observations and all next 5 target observations are valid.
- Common 80% calendar cutoff: 2025-11-25.
- Purge dates: 2025-11-26, 2025-11-28, 2025-12-01, 2025-12-02, 2025-12-03.
- Evaluation begins: 2025-12-04.
- Leave one complete symbol out for evaluation; it contributes zero fitting rows.

Scale-normalized Log-HAR:

```text
RV1_t  = RV_t
RV5_t  = mean(RV[t-4:t])
RV22_t = mean(RV[t-21:t])
Y5_t   = mean(RV[t+1:t+5])

xD = log(RV1_t / RV22_t)
xW = log(RV5_t / RV22_t)
z  = log(Y5_t / RV22_t)

forecast = RV22_t * exp(z_hat)
```

Models:

- Global Ridge-HAR: all non-held-out symbols, both markets.
- Market Ridge-HAR: only non-held-out symbols from the held-out symbol's market.
- Ridge alpha fixed at 1.0.
- Primary loss: QLIKE.
- Delta = market QLIKE - global QLIKE; negative favors market-specific.
- Uncertainty: paired moving-block bootstrap over dates, block length 20, 5,000 replicates.

## Results

| Held-out | Market | N eval | Global QLIKE | Market QLIKE | Delta | 95% block-bootstrap CI |
|---|---|---:|---:|---:|---:|---:|
| GOOGL | US | 198 | 0.243864 | 0.244687 | +0.000823 | [-0.001715, +0.004054] |
| NVDA | US | 198 | 0.111620 | 0.112936 | +0.001316 | [+0.000659, +0.002814] |
| QQQ | US | 198 | 0.181829 | 0.183743 | +0.001915 | [-0.000343, +0.003863] |
| TSM | US | 198 | 0.157131 | 0.160214 | +0.003084 | [+0.000847, +0.005896] |
| 2330 | Taiwan | 191 | 0.141952 | 0.140722 | -0.001230 | [-0.005168, +0.002744] |
| 2317 | Taiwan | 191 | 0.160895 | 0.169209 | +0.008313 | [+0.000416, +0.015966] |
| 2454 | Taiwan | 123 | 0.156651 | 0.155385 | -0.001267 | [-0.002415, -0.000564] |

Date-level paired summaries:

| Scope | Mean delta | 95% block-bootstrap CI | Reading |
|---|---:|---:|---|
| Overall | +0.002047 | [+0.001121, +0.003386] | global favored |
| U.S. | +0.001784 | [+0.000668, +0.003250] | global favored |
| Taiwan | +0.002686 | [-0.000635, +0.006306] | inconclusive |

## Ruling

This pilot does not support market-specific Ridge-HAR promotion.

- U.S. unseen-symbol transfer favors the shared/global model.
- Taiwan results are not stable across unseen symbols: 2454 favors market-specific, 2317 favors global, and 2330 is
  inconclusive.
- The earlier 2330-specific measurement/model behavior is therefore insufficient evidence for a Taiwan-specific production
  parameter set.

This result does not yet promote global Ridge-HAR as the final Pine model. The next narrow experiment should compare the
global Ridge-HAR forecast against the existing causal per-symbol HAR and GARCH forecasts already contained in the same
TradingView exports, using the same held-out evaluation window.
