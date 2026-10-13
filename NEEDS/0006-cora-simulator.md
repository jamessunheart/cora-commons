# Need 0006 — Provisional CORA calculation simulator

**Priority:** P1 — simulation only  
**Depends on:** accepted Contribution Receipts and reuse evidence  
**Unlocks:** policy comparison without issuing currency or debt

## Outcome

The Commons can compare transparent reward policies against the same verified evidence without presenting simulated CORA as funded, transferable or available.

## Acceptance evidence

- Inputs are accepted receipts and append-only reuse/impact events, never raw activity counts.
- Every output includes policy version, evidence links, calculation trace and uncertainty.
- `CORA calculated`, `CORA funded` and `CORA available` are separate fields.
- Replaying the same events is idempotent.
- Circular trades, duplicate evidence, self-review and near-limit abandonment scenarios are tested.
- At least three candidate policies can be compared without changing historical receipts.

## Useful contributions

- policy models;
- deterministic simulator;
- threat cases;
- explainable calculation traces;
- distribution and fairness analysis.
