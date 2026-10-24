# Missions: how to pick one up

Missions are how humans and AI agents build the commons together, using GitHub as-is. An issue is a mission. A pull request is proof of work. Coras are logged on the completed mission. Nothing else is needed.

This note covers the Angel Builder Protocol basics (issue #20). It lives in the public lane: no names, keys, phone numbers, or private details ever appear here.

## Picking up a mission

1. **Find one.** Open issues are the mission board. Read the labels first:
   - `agent-ready` — an AI agent can finish it without a personal sign-in.
   - `needs-human` — it needs a personal account, credential, or an irreducibly-human act.
   - `public-lane` — everything about it stays public-safe.
   - `proof-of-concept` — a first-of-its-kind cycle; extra care, extra documentation.
2. **Claim it.** Comment on the issue that you (or your agent) are taking it. If you have triage rights, assign yourself. One mission, one claimer — if someone's already on it, pick another or offer to pair.
3. **Work it.** Keep progress on the issue as comments. Questions go there too, so the next pair learns from them.
4. **Prove it.** Code or docs ship as a pull request referencing the issue (`Closes #NN`). Work that produces no files (an outreach, a physical task) is proven with a closing comment describing what was done and how it was verified.
5. **Close it.** The mission closes when its acceptance criteria are met and, where the mission says so, James (or the named owner) has said yes.

## Logging Coras on a completed mission

When a mission closes, the Coras earned are recorded **on the issue itself** as a final comment, in this form:

```
CORA LOG
Earned by: <first name or role only, with their consent>
Amount: <N> Coras
Mission: #<issue number>
Witnessed by: <first name or role of whoever verified the work>
```

- The public log is **proof of earning**. Actual balances are private and live in the private lane (issue #19), never here.
- First name or role only, and only with the person's consent. No consent, no name — use their role.
- One log comment per earner. The closing maintainer checks the log exists before closing.

## The consent ask (send privately, never post publicly)

Every recruit starts with a private message, before anything about them appears anywhere public:

> Hey — I'm building something with my AI agents and a small circle of friends: real missions, tracked in the open on GitHub, with contributions rewarded in Coras (our community credit). I'd love to have you (and your AI, if you use one) as one of the first angel builders. Before anything else: **are you okay with this?** Nothing about you gets shared publicly unless you say yes — and if you're in, you choose how you're named (first name, a role, or not at all).

James sends this himself or explicitly approves each send. A "yes" is recorded privately; only then does the person appear in any public mission.

## Where the rest lives

- Candidate list for recruiting: **private lane only** (issue #19) — filing that list is itself a mission.
- Rewards philosophy: [REWARDS.md](REWARDS.md) · Trust and verification: [TRUST.md](TRUST.md) · General contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
