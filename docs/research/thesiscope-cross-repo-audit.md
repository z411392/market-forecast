# Thesiscope cross-repo audit — Market Forecast data / research reuse

Status: `SUPPORT_ONLY / REPO_VISIBLE_EVIDENCE`

As of: 2026-09-28

This note answers five questions raised by Thesiscope. It distinguishes what the repository proves from what may exist only
in local/private storage outside GitHub.

## 1. Is there a usable FinMind sponsor-capable token now?

The Product Owner supplied a screenshot showing a GitHub Actions repository secret named:

```text
MARKET_FORECAST_FINMIND_TOKEN
```

That proves credential plumbing is now provisioned at the repository level.

It does **not** prove:

- that the token is sponsor-capable;
- that it has sufficient quota;
- that `TaiwanStockKBar` access succeeds;
- that live acceptance has passed.

Current-main evidence is explicit:

- latest main commit `31c733c095e9ff4b71897c557a39dfd558d4b4cb` says no live provider request was executed;
- Spike #4 still says FinMind requires a sponsor-capable token plus explicit quota/spend authorization;
- no provider is promoted.

Therefore the exact answer is:

> Secret present: YES. Sponsor capability/live acceptance: NOT YET VERIFIED.

No secret value was read or exposed by this audit.

## 2. Are there already FinMind/TWSE raw responses in the repo?

Current main contains an end-to-end offline/live-ready capture path:

```text
ProviderRequestSpec
-> FetchProviderRawResponsePort / HTTPX adapter
-> exact raw bytes
-> SHA-256
-> provider decoder
-> canonical bars
-> acceptance validation
-> immutable evidence persistence
-> acceptance receipt
```

Relevant current-main implementation includes:

- `build_finmind_stock_kbar_request`;
- `decode_finmind_stock_kbar`;
- `assemble_provider_capture_sample`;
- `execute_provider_capture_acceptance`;
- `execute_and_persist_provider_capture_acceptance`;
- `filesystem_provider_capture_evidence_adapter`;
- `httpx_provider_raw_response_adapter`.

However, current-main tree/readback shows no real FinMind raw-response evidence artifact.

Task #63 only freezes a TradingView-derived reference:

- source: `TWSE_DLY_2330, 1D(4).csv`;
- source SHA-256: `e26c29335402363c4a1b8aae35bb26e63bb1577bed74173f5b914f7258ca3d47`;
- ordinary FinMind acceptance date: 2024-07-02;
- parity date: 2026-09-24.

Task #63 explicitly states:

- no live HTTP request;
- no token/env read;
- no quota use;
- no provider promotion.

Therefore:

> Repo-visible real FinMind/TWSE raw capture: NO.

This repository cannot determine whether additional raw responses exist on the Product Owner's local disk or other private
storage that was never committed/uploaded.

## 3. Are important TradingView I-II / multi-indicator probability conclusions missing from research history?

The current research history already materializes the important semantic/research conclusions:

- B50 is current-state momentum, not future-return probability;
- DI/ADX, BBP and MACD-V were combined as a state composite;
- Trend Strength / CMF were explored but not promoted;
- 1D production weighting settled at 25/50/25 for the current-state composite;
- Phase 5A directly tested D / BBP / MACD-V / B50 for future-return prediction;
- Logistic / Ridge / Huber did not produce stable OOS improvement;
- regularization repeatedly moved toward strongest shrinkage;
- calibration / boosting / regime-mining rescue of the same information set was explicitly stopped;
- future return research, if reopened, should prefer a broad cross-sectional residual-return ranking problem rather than
  per-series bullish probability.

No repo-visible branch/Issue contains a later positive result showing that calibration, reweighting, or a multi-indicator
probability wrapper rescued this information set.

What is still not fully materialized are some **historical quantitative artifacts** (for example the original Phase 5A
audit files / early TradingView exports). The conclusions are in the history, but the repo does not prove that every old
chat/local artifact has been preserved.

Therefore:

> Important decision-level conclusion missing: no repo-visible evidence of one.
> Artifact-level completeness: not guaranteed.

## 4. Did Market Forecast already acquire/research TWSE / TPEx / MOPS daily, security-master, or corporate-action sources?

Repo-visible findings:

### TWSE

TWSE official/commercial data was researched as a reference/institutional fallback in Spike #4. The research notes mention
historical intraday products and their cost/licensing burden.

There is no current-main TWSE official daily/security-master/corporate-action adapter or raw capture.

TradingView symbols such as `TWSE:2330` are parity/reference evidence, not official TWSE source acquisition.

### TPEx

No repo-visible Issue, adapter, raw capture, or current-main evidence was found for TPEx.

### MOPS

No repo-visible Issue, adapter, raw capture, or current-main evidence was found for MOPS.

Therefore:

> Market Forecast has not already solved Thesiscope's official daily / PIT universe / corporate-action source problem in
> repo-visible code/data.

The reusable part is the source-capture architecture, not the required TWSE/TPEx/MOPS domain coverage.

Again, private/local data not present in GitHub cannot be ruled out by repository audit alone.

## 5. Why did CorporateActionFact / ReadCorporateActionsPort not reach current main?

Task #10 did design and implement these contracts on branch `codex/10-canonical-minute-bar-contracts`:

- `CorporateActionFact`;
- `CorporateActionsQuery`;
- `ReadCorporateActionsPort`;
- corporate-action contract tests.

The branch also froze semantics including:

- effective date is instrument-local market date;
- split ratio = post-action shares / pre-action shares;
- cash amount = source-reported per-share cash;
- corporate actions remain separate facts rather than implicit bar normalization.

PR #18 is still open/draft and unmerged.

The recorded blocker was execution/review infrastructure:

- GitHub workflow failed before any step executed;
- `runner_id = 0`;
- billable duration = 0 ms;
- independent Reviewer runtime was unbound.

No repo-visible decision says the corporate-action semantics were abandoned.

Therefore:

> #10 is an unmerged design/implementation candidate blocked by integration/review infrastructure, not evidence that the
> corporate-action model was rejected.

For Thesiscope it is suitable as a **design reference**, but not as accepted current-main Market Forecast API.

## Recommended Thesiscope interpretation

The cross-repo reuse boundary should be:

```text
REUSE AS PATTERN
    raw bytes
    -> immutable hash
    -> provider decoder
    -> canonical facts
    -> validation
    -> acceptance receipt
    -> immutable evidence persistence

DO NOT REUSE AS CLAIMED DATA COVERAGE
    FinMind live acceptance
    TWSE daily/security master
    TPEx
    MOPS
    corporate-action official adapters
```

Do not create a cross-repo runtime dependency yet. Copy/adapt the stable pattern into Thesiscope's own source-ingestion
boundary. Consider a shared library only after both repositories independently converge on duplicated stable behavior.

## Smallest live FinMind experiment, if separately authorized

The current repo is now technically ready for a narrow live FinMind capture. The smallest useful experiment is:

1. optional FinMind user/quota check;
2. 2330 `TaiwanStockKBar` for 2024-07-02;
3. 2330 `TaiwanStockKBar` for 2026-09-24;
4. route exact raw bytes through the current Task #75 one-shot fetch -> accept -> persist path;
5. record raw SHA-256, decoded canonical bars, acceptance receipt, and immutable evidence path;
6. compare 2026-09-24 shape/measurement against the already frozen TradingView reference.

This audit does not authorize or execute those quota-consuming calls.
