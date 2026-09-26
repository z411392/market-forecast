# Task #13 — Final Pine Comparator Pilot

Status: PILOT_PROMOTION_RULING

## Purpose

Compare the shared unseen-symbol Ridge-HAR candidate with the causal HAR/GARCH forecasts already exported by the
TradingView Phase 4A research script. Every model is scored on the same held-out evaluation rows and the same future-H=5
realized-variance target.

## Alignment

The Pine forecast is taken from the origin date. Python independently reconstructs the next-five-session actual target from
`P4_RV_WHOLE_DAY_5M`.

As a cross-check, Python-recomputed HAR QLIKE at an origin matches the exported `P4_QLIKE_HAR` five bars later, confirming
that the matured H=5 target is aligned correctly.

## Mean QLIKE

| Held-out | Global Ridge-HAR | Pine HAR | Pine GARCH | Pine HARQ | EWMA | Naive |
|---|---:|---:|---:|---:|---:|---:|
| GOOGL | 0.243996 | 0.184602 | 0.225043 | 0.185072 | 0.244632 | 0.317753 |
| NVDA | 0.111572 | 0.145288 | 0.134016 | 0.142725 | 0.096118 | 0.155391 |
| QQQ | 0.181825 | 0.142876 | 0.155744 | 0.144833 | 0.176851 | 0.268999 |
| TSM | 0.157013 | 0.126194 | 0.120562 | 0.126817 | 0.134083 | 0.235730 |
| 2330 | 0.142007 | 0.154843 | 0.189887 | 0.154808 | 0.139787 | 0.178993 |
| 2317 | 0.161229 | 0.154588 | 0.149228 | 0.155380 | 0.191205 | 0.159321 |
| 2454 | 0.156929 | 0.146265 | 0.282379 | 0.149711 | 0.154112 | 0.208687 |

## Paired 20-session moving-block bootstrap

Difference is first model minus second; negative favors the first model.

| Scope | Comparison | Mean delta | 95% CI |
|---|---|---:|---:|
| Overall | HAR - Global | -0.013993 | [-0.044484, +0.003130] |
| Overall | GARCH - Global | +0.008681 | [-0.008143, +0.026063] |
| Overall | HAR - GARCH | -0.022675 | [-0.053313, -0.006911] |
| Overall | HARQ - HAR | +0.000506 | [-0.000383, +0.001776] |
| Overall | EWMA - HAR | +0.012462 | [+0.000081, +0.034094] |
| U.S. | HAR - Global | -0.023861 | [-0.054961, -0.002899] |
| U.S. | HAR - GARCH | -0.009101 | [-0.031495, +0.007185] |
| Taiwan | HAR - Global | +0.000876 | [-0.052041, +0.035038] |
| Taiwan | HAR - GARCH | -0.040721 | [-0.108739, +0.001592] |

Bootstrap uses 5,000 replicates, 20-session blocks, and deterministic seed `20260926`.

## Ruling

For this supplied 4-U.S. + 3-Taiwan pilot:

- Do not promote market-specific Ridge-HAR parameters.
- Do not promote shared/global Ridge-HAR over the existing causal Pine HAR.
- HAR beats GARCH overall with a block-bootstrap interval entirely below zero.
- HARQ does not show stable incremental value over HAR.
- EWMA can win isolated symbols but does not support a ticker-specific selector and is worse than HAR overall.

TradingView handoff:

- primary forecast: causal Pine HAR H=5 expected volatility;
- optional diagnostic: GARCH;
- HARQ: research-only / off by default;
- no market-specific or ticker-specific model switch;
- no bullish probability or Buy/Sell semantics.

This is a pilot promotion ruling, not a universal claim across all securities or markets.
