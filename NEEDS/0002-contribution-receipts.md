# Need 0002 — Append-only Contribution Receipts

**Priority:** P0 — build now  
**Depends on:** founding repository and contribution workflow  
**Unlocks:** verification, attribution, reuse evidence, later CORA simulation

**Implementation status:** v0.5 validator, schema, recognition form and automated checks implemented; independent external review is still required before this capability is accepted as a BRICK.

## Outcome

Every delivered contribution can produce one durable, machine-readable receipt without implying that it is accepted, funded or rewarded.

## Minimum record

- receipt id and schema version;
- Need and agreement links;
- human and agent contributors with stated roles;
- artifact and immutable version or commit;
- evidence state and evidence links;
- known and unknown capital consumed;
- limitations, dependencies and risks;
- independent reviewer and decision;
- append-only reuse, impact and reward events.

## Acceptance evidence

- A documented JSON schema and human-readable example exist.
- A deterministic validator accepts a valid receipt and rejects missing attribution, self-acceptance and invalid state transitions.
- Corrections append superseding events instead of silently rewriting settled history.
- Tests cover duplicate ids, idempotent replay and unknown reward/funding state.
- No receipt is treated as CORA available or a payable debt.

## Useful contributions

- schema design;
- validator and tests;
- privacy/threat review;
- example receipts;
- migration and versioning design.
