# Need 0008 — Authenticated contribution gateway

**Priority:** P2 — scale only after the bounded pilot  
**Depends on:** proven schemas, workflows and authority boundaries  
**Unlocks:** governed MCP writes and federation across local Commons

## Outcome

Authorized humans can let agents prepare and submit narrowly scoped contribution events without exposing treasury, private beneficiary or sovereign governance powers.

## Acceptance evidence

- Human and agent identities are distinct and attributable.
- Permissions are scoped by action, resource, Commons node and expiration.
- Every write is authenticated, rate limited, idempotent and audit logged.
- High-consequence actions require explicit human approval and cannot be bundled into general agent access.
- Revocation, dispute, spam and compromised-agent scenarios are tested.
- Load testing establishes measured capacity before any claim of supporting thousands of teams.

## Useful contributions

- authentication and authorization model;
- signed event API;
- MCP write-tool threat model;
- audit and revocation design;
- federation and load testing.
