# Taiwan RV Sampling Decision Analysis

Task: #89  
Parent measurement task: #12  
Algorithm under audit: `rv-core-v1+xtai-closing-auction-v4`

## Decision

`TAIWAN_CANONICAL_SAMPLING = INCONCLUSIVE`

Operationally:

- 5m remains the preregistered practical reference.
- 5m is not promoted to the canonical frozen Taiwan target.
- 10m and 15m remain sensitivity measurements.
- Neither 10m nor 15m is promoted.
- Forecast/model QLIKE is not permitted to choose among these measurement definitions.
- A noise-robust measurement benchmark is required before Taiwan canonical target freeze.

## Why this is not a 5m freeze

The research history preregistered 5m as the primary practical reference before the current provider-backed Taiwan panel. That protects the analysis from post-hoc model-score selection, but preregistration alone does not prove that 5m is an unbiased or statistically preferable measurement of latent integrated variance.

The completed Taiwan v4 panel shows persistent cross-frequency level sensitivity:

| Symbol | Geo. bias 5m vs 10m | Geo. bias 5m vs 15m |
|---|---:|---:|
| 2330 | +22.1571% | +36.9188% |
| 2317 | +14.7502% | +25.5794% |
| 2454 | +13.1161% | +22.6530% |
| Panel median | +14.7502% | +25.5794% |

This is not a negligible perturbation.

At the same time, agreement is high enough that the three definitions are clearly measuring the same broad volatility state:

| Metric | 5m vs 10m | 5m vs 15m |
|---|---:|---:|
| Panel-median Pearson log-RV | 0.96476 | 0.94274 |
| Panel-median Spearman RV | 0.94880 | 0.90901 |

Therefore the problem is primarily measurement scale / microstructure sensitivity, not a complete loss of volatility-state information.

## Why this is not a 10m or 15m promotion

The current audit contains no independent latent-variance truth.

Observing

`RV_5m > RV_10m > RV_15m`

does not identify which estimator is closest to latent integrated variance.

Possible explanations include:

- upward microstructure-noise contamination at finer sampling;
- genuine variation lost by coarser sampling;
- both mechanisms simultaneously.

No quantitative threshold for “acceptable” level bias was preregistered. Introducing one after observing the panel would be post-hoc measurement selection.

Therefore lower measured variance is not itself evidence that 10m or 15m is superior.

## Previous-tick impact

Task #86 v4 resolves valid no-trade fixed-grid intervals using previous-tick calendar-time sampling with explicit provenance and staleness bounds.

In the accepted 3-symbol × 252-session panel:

- 2330: no previous-tick samples;
- 2317: no previous-tick samples;
- 2454:
  - 5m: 8 boundaries across 5 sessions;
  - 10m: none;
  - 15m: none.

For 2454 5m this is approximately 0.0588% of all sampled boundaries.

Thus previous-tick handling is required for correctness, but it is too rare to explain the broad double-digit 5m-vs-coarser level bias.

## Whole-day measurement remains necessary

Median overnight-variance shares are material and vary with the intraday sampling denominator:

| Symbol | 5m | 10m | 15m |
|---|---:|---:|---:|
| 2330 | 28.18% | 33.75% | 39.18% |
| 2317 | 18.12% | 21.32% | 23.97% |
| 2454 | 20.12% | 24.48% | 23.97% |

The canonical decision must therefore remain a whole-day variance decision rather than an intraday-only comparison.

## Measurement-theory check

The fixed-grid evidence is consistent with the classical market-microstructure literature:

1. Classical realized variance can be biased/inconsistent for latent integrated variance under microstructure noise at sufficiently fine sampling.
2. The MSE-optimal classical-RV sampling interval can be finite and vary across assets and time.
3. Common 5-minute sampling is a practical heuristic, not a universal ground truth.
4. Noise-robust estimators such as realized kernels or multi-scale estimators are specifically designed to estimate variation without choosing a final target solely by one arbitrary sparse grid.

References:

- Bandi & Russell (2008), *Microstructure Noise, Realized Variance, and Optimal Sampling*, Review of Economic Studies.
- Aït-Sahalia, Mykland & Zhang (2005), *How Often to Sample a Continuous-Time Process in the Presence of Market Microstructure Noise*, Review of Financial Studies.
- Barndorff-Nielsen, Hansen, Lunde & Shephard (2008), *Designing Realized Kernels to Measure the ex post Variation of Equity Prices in the Presence of Noise*, Econometrica.

## Ex-ante decision rule

Use the following rule before any frequency promotion:

1. Keep the preregistered 5m definition as the continuity/reference measurement.
2. A canonical freeze requires either:
   - economically small cross-frequency sensitivity, or
   - an independent measurement-theory criterion identifying the preferred estimator.
3. Do not invent a post-hoc level-bias cutoff from the observed Taiwan panel.
4. Do not use forecast QLIKE/model performance to choose the target measurement.
5. If systematic level sensitivity is material and no independent truth criterion exists, declare the canonical fixed-grid frequency inconclusive.

Applying that rule gives the current decision:

`TAIWAN_CANONICAL_SAMPLING = INCONCLUSIVE`.

## Required next work

Build a provider-backed Taiwan noise-robust benchmark before canonical target freeze.

Candidate families to evaluate without forecast-score selection:

- realized kernel;
- two-scale / multi-scale realized variance;
- explicit microstructure-noise / MSE-optimal sampling estimation.

The benchmark task should first select an estimator from measurement theory and source feasibility, then compare 5m/10m/15m whole-day measurements against that independent benchmark.

The immediate question is measurement identification, not broader model search and not the later 30+30 confirmatory universe.

## Boundaries

This analysis does not claim:

- 5m is wrong;
- 10m or 15m is correct;
- Taiwan requires market-specific forecasting parameters;
- U.S. measurement is frozen;
- the cross-market canonical target is frozen.

It only concludes that the current Taiwan fixed-grid panel is insufficient to identify a canonical sampling frequency.
