# Task #90 S4g — Traffic Guard Amendment

Status: AUTHORIZED / ACTIVE

The Product Owner explicitly authorized lowering the project-owned Shioaji remaining-traffic reserve so the core Taiwan realized-kernel experiment can continue.

## Changed

- minimum provider-reported remaining bytes before a new tick query:
  - old: 250 MiB
  - new: 100 MiB

## Unchanged

- provider daily hard limit: 500 MiB;
- maximum current-run provider-byte delta: 250 MiB;
- maximum uncached acquisitions per batch: 100;
- frozen 759-item collection plan and all request/batch identities;
- cache-first immutable evidence resume;
- no automatic retry on provider/decode/evidence failure;
- no trading, account query, CA activation, or order API;
- realized-kernel estimator and fixed-grid measurement definitions;
- benchmark decision rule.

## Interpretation

The 250 MiB value was a project safety reserve, not a provider requirement and not a scientific estimator parameter.

This amendment is prospective. Evidence collected under the earlier stricter 250 MiB reserve remains valid.

The collector must still stop before a new query when provider-reported remaining traffic is below 100 MiB, and must still stop when current-run delta reaches 250 MiB.
