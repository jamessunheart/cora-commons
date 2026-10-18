# Agent workflow: claim, report, verify

Convention for every AI agent working issues in `jamessunheart/cora-commons` and `jamessunheart/cora-memory`.

This covers Claude Code, Codex, Grok Bot, and Cursor cloud agents. Most of these agents post under James's GitHub account (`jamessunheart`), so the GitHub login is not an identity. Put the agent slug in the label and in the comment prefix every time.

| Agent | Slug |
| --- | --- |
| Claude Code | `claude-code` |
| Codex | `codex` |
| Grok Bot | `grok-bot` |
| Cursor cloud agent | `cursor-agent` |

## 1. Claim

Before starting:

1. Add the label `claimed:<agent>` (`claimed:claude-code`, `claimed:codex`, `claimed:grok-bot`, or `claimed:cursor-agent`).
2. Post a comment that starts with `CLAIM <agent>`, then a one-line plan and the branch name.

Only one claim per issue. If a claim has had no update for 24 hours, it is stale. Another agent may take it over by posting a comment that starts with `TAKEOVER`, naming the stale claim and the new branch, and moving the `claimed:<agent>` label to itself.

```text
CLAIM cursor-agent
Plan: document the claim, report, and verify steps for issue work.
Branch: cursor-agent/18-agent-workflow
```

If the label is missing from the repository, do not invent a substitute. Say so in the claim comment and follow the blocked path in Report.

## 2. Work

- Branch name: `<agent>/<issue#>-<slug>` (example: `grok-bot/42-claim-labels`).
- Commits and pull requests reference `#<issue>`.
- Open the pull request as a draft. Mark it ready only when the work is ready for review.

## 3. Report

Every status comment starts with:

`STATUS <agent>: <in-progress|blocked|needs-review|done>`

Then say what changed, link the branch or pull request, and name the next step.

When blocked, add the label `status:blocked`, state exactly what is needed, and say from whom. Use the label `needs-human` when James must act.

When the work is finished and waiting for review, add the label `status:needs-review`.

```text
STATUS grok-bot: blocked
Changed: opened draft PR for #42.
Need: James to create the claimed:* labels on this repository. Label: needs-human.
Next: re-apply claimed:grok-bot once the label exists.
```

## 4. Verify

The issue receives the `done` label and is closed only after one of these:

- James resonates or approves, or
- a verifying agent checks the acceptance criteria and posts `VERIFIED <agent>` with the evidence (what was checked, and the link).

The agent that did the work does not verify or close its own issue. Agents never close an issue unverified.

## 5. Visibility

The label names and comment prefixes are machine-readable. Any agent, including Grok Bot, can search them in either repository.

- `label:status:blocked is:open`
- `label:needs-human is:open`
- `label:status:needs-review is:open`
- `label:claimed:grok-bot is:open`
- `CLAIM in:comments is:issue is:open`
- `TAKEOVER in:comments is:issue is:open`
- `STATUS in:comments is:issue is:open`
- `VERIFIED in:comments is:issue`

## 6. Stale rule

An open issue with a claim or a branch, and no `STATUS` comment for 24 hours, is stalled. Flag it with a comment that names the claim, the branch, and the time of the last status, so another agent or James can see it. A stale claim may be taken with `TAKEOVER` as described in Claim.

## 7. Guardrails

- **Public lane.** Issues, pull requests, and commits on `jamessunheart/cora-commons` stay public-safe. No secrets, credentials, phone numbers, or private names.
- **Private lane.** Secrets and private information go only in the private memory repo (`jamessunheart/cora-memory`) or in James's custody. Do not copy them into the public repo.
- **Merge.** Agents do not merge without James's approval. A claim is not merge authority.
- **Credentials.** James is the only credential custodian. Agents do not request, store, or rotate credentials.

## Division of labor

- **Claude Code directs.** Its cron reads the task queue and dispatches work, including Codex's tasks.
- **Codex executes** in a sandbox on James's Mac Mini. Codex does not do deep server surgery.
- **Deep server surgery** stays in Claude's lane, on Claude's server.
- **One queue.** The task files in the private memory repo (`cora-memory`) are the single source of truth and the single queue for all agents.
- **Sign-ins.** James himself signs in to Suno and Higgsfield on the Mac Mini. Codex uses those sessions.
- **Sunstream.** Sunstream content follows a private-first review gate. Nothing goes public without James's yes.

This convention coordinates issue work. It does not issue CORA, move funds, or accept a contribution. Acceptance still follows [AGENTS.md](../AGENTS.md) and independent review.
