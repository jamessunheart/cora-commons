# Need 0004 — Independent verification queue

**Priority:** P0 — build now  
**Depends on:** Needs 0002 and 0003  
**Unlocks:** accepted BRICKS, trusted reuse and reward evidence

## Outcome

Delivered work enters a transparent review queue and cannot become an accepted BRICK through self-approval.

## Acceptance evidence

- Review records identify the agreement, delivery, reviewer, test method and evidence state.
- The system rejects contributor/reviewer identity overlap unless a documented exception is separately approved.
- Results distinguish `EXISTS`, `RENDERS`, `WORKS` and `USABLE`.
- Rejection and requested-revision reasons are preserved.
- A second participant can reproduce the review from public-safe evidence.
- Acceptance creates a Contribution Receipt event; it does not issue CORA automatically.

## Useful contributions

- reviewer workflow;
- identity and conflict-of-interest rules;
- reproducible test templates;
- review queue interface;
- adversarial testing.
