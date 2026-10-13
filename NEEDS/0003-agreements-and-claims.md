# Need 0003 — Agreement and work-claim registry

**Priority:** P0 — build now  
**Depends on:** Need records  
**Unlocks:** parallel teams, reduced duplicate work, explicit expected return

## Outcome

A human-agent team can claim a bounded piece of a Need under a time-limited agreement, while other participants can see scope, dependencies and availability without receiving authority over private systems.

## Acceptance evidence

- A versioned agreement schema records scope, exclusions, evidence, cost ceiling, expected return, participants and agent authority.
- Claims have `PROPOSED`, `AGREED`, `ACTIVE`, `BLOCKED`, `DELIVERED`, `RELEASED` and `EXPIRED` states.
- Claims expire or can be released without deleting history.
- Concurrent or overlapping claims are visible and never silently overwrite each other.
- A deterministic view shows open, claimed and blocked work.
- Posting, assignment and state changes still require an authenticated human action.

## Useful contributions

- state-machine design;
- schemas and fixtures;
- conflict detection;
- GitHub-based prototype;
- accessibility and newcomer testing.
