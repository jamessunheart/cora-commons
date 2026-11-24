# Cora Commons

**Bring what you have. Bring what you need. Build intelligence everyone can use.**

Cora Commons is an open, human-directed effort where people and their AI agents turn real needs into verified, reusable capabilities called **BRICKS**.

> **Current design:** [AGENT-COMMONS.md](AGENT-COMMONS.md) explains the Agent Commons offer and how proven agents become BRICKS.

The working loop is:

`Need -> Match -> Agree -> Build -> Verify -> Reuse`

## Start here

You do not need a special Cora account or a particular AI agent.

1. Open [CONNECT.md](CONNECT.md) and give its starter prompt to your agent.
2. Let the agent read the canonical brief and suggest one bounded next contribution.
3. Complete a [connection check](https://github.com/jamessunheart/cora-commons/issues/new?template=connect.yml) or choose an existing Need.
4. Agree on scope, acceptance evidence and any expected return before substantial work.
5. Work in a fork or branch and submit a pull request with evidence, cost and limitations.
6. An independent participant reviews the contribution before it becomes an accepted BRICK.
7. Submit accepted work for a validator-approved [Contribution Receipt](CONTRIBUTIONS/README.md) so its attribution becomes durable Commons history.

If the agent finds a weakness, it should help convert the finding into a bounded solution through [`IMPROVE.md`](IMPROVE.md), not merely produce a list of problems.

## Where truth lives

Cora Commons is the shared, public layer of the network. Each participant keeps their own notes in whatever app they choose (Notion, Obsidian, plain files) and decides there what stays private and what is contributed here. As the network grows, this repository and its private counterparts become the single source of truth for shared work; nothing private belongs here.

## Cora Steward triage

The repository includes a draft-only **Cora Steward** workflow. A GitHub Action
turns new issue, comment and pull-request activity into a review packet with
observed attribution, evidence signals, missing fields, independent-review
routing and a clear authority boundary. It can identify missing information and
prepare a receipt, but it cannot accept work, issue CORA, spend funds, merge a
receipt or resolve a dispute. The packet is uploaded as an Actions artifact and
shown in the job summary. This is intentionally deterministic before adding
more expensive model-based review.

For the ordered economic build, read [`CAPITAL_COMMONS.md`](CAPITAL_COMMONS.md). The current P0 work is Contribution Receipts, agreement/work claims and independent verification—not token issuance or treasury automation.

Agents that prefer structured discovery can read [`commons.json`](commons.json).

## Worker healer

From the repository root, run `python heal.py --workers sample.json` with
Python 3.11 or newer. Each run checks one snapshot against a single UTC time,
prints the stuck worker IDs, and writes `heal.json` in the current working
directory. A crashed worker or a heartbeat older than ten minutes qualifies.
Exactly ten minutes is still healthy for a running worker. Supply a timestamp
with a UTC offset (or `Z`). A crashed worker may omit its heartbeat.

The default is a dry run. Add `--apply` to execute the planned argument lists
from `restart_commands.json` beside the script. The shipped commands only
print synthetic restart messages. Use `--config PATH` to select a trusted
map keyed by worker ID. Invalid input or a missing required command stops the
run before it replaces the report or executes any command. The report records
the plan. If an applied command fails, the healer exits with an error and
skips the remaining commands.

Use separate files for the worker snapshot, command map, and output. The healer
rejects either input if it refers to the same file as `heal.json`, including
through a link. For synthetic governor commands, the application allows up to
4 KiB per encoded argument and 16 KiB per command, including the executable.
The command total counts one terminating NUL byte per argument. These bounds
keep synthetic commands small. Operating-system launch limits can vary.

For a dry run every two minutes, set the checkout and Python paths for your
host in this crontab entry. It writes `/absolute/path/to/cora-commons/heal.json`.

```cron
*/2 * * * * cd /absolute/path/to/cora-commons && /usr/bin/python3 heal.py --workers sample.json
```

Each run reads the snapshot again. With `--apply`, a worker that still appears
stuck in the next snapshot will receive its configured command again.

## MCP connection

The repository includes a read-only Cora Commons MCP server. It exposes the public manifest, participation guide, agent instructions and Needs, plus tools for understanding the Commons and finding a bounded contribution path. It cannot issue CORA, move funds, post to GitHub or access private systems.

Connect to `https://fullpotential.com/mcp`, or see [`MCP.md`](MCP.md) for local installation, host configuration and the verified interface.

## Task picker

`picker.py` picks the next open task from `tasks.json` and records the result on a side branch instead of `main`. It works in its own git worktree (a second folder linked to the same repository), so the main checkout is never written to. Each run makes at most one commit on the side branch, and only when the picker state changed, so frequent runs no longer crowd the history of `main` or collide with open pull requests.

```bash
python3 picker.py --repo /srv/cora-commons --branch picker/state
```

- `--worktree` sets the worktree folder. The default is a folder next to the repository named `<repo name>-picker`; a folder inside the main checkout is refused.
- `--tasks` sets the tasks file. The default is `<repo>/tasks.json`; the file is only read.
- A run prints `committed <short sha>` or `no changes`. It exits non-zero with a message when the repository or tasks file is invalid, or when the branch is already checked out elsewhere, including in the main checkout.

Task selection is a placeholder that works on synthetic data: the open task with the lowest `priority` is picked, and ties are broken by `id` in text order.

### Run every minute with cron

```cron
* * * * * cd /srv/cora-commons && python3 picker.py --repo /srv/cora-commons --branch picker/state >> /var/log/cora-picker.log 2>&1
```

The five fields before the command are minute, hour, day of month, month and day of week. A `*` in all five means every minute of every day. `>> /var/log/cora-picker.log 2>&1` appends both normal output and errors to one log file. Cron is available on Linux and macOS; Windows hosts use Task Scheduler instead.

### Merge the side branch on a schedule

Once a day, at 02:15 in this example, the collected state is merged into `main` from a clean checkout of `main`:

```cron
15 2 * * * git -C /srv/cora-commons merge --no-ff picker/state -m "chore: merge picker state" >> /var/log/cora-picker.log 2>&1
```

`--no-ff` always creates a merge commit, so each day's picker commits arrive on `main` as one visible merge. The merge creates a commit, so the server's git user needs a name and email configured. If uncommitted changes in the checkout would be overwritten, git refuses the merge; if the merge conflicts, git leaves it unfinished until a person resolves it or runs `git merge --abort`. Either way the error is in the log. Teams that merge only through pull requests can instead open one pull request per day from `picker/state` into `main`.

## Static publisher

`publish.py` turns a folder of Markdown pages into a static site. Only pages with `published: true` are written. `verify.py` then checks that each page loads without cookies and shows the expected title.

### Page format

Each `.md` file directly inside the source folder starts with front matter:

```markdown
---
title: Welcome to the Commons
slug: welcome
published: true
---
# Welcome
```

- `published` is required and must be exactly `true` or `false`, in lowercase.
- A published page needs a non-empty `title` and a `slug` made of lowercase letters, digits and single hyphens, at most 64 characters. Two published pages cannot share a slug.
- One pair of matching quotes around a value is removed. Other keys are ignored. A key used twice is an error. Drafts are not checked for `title` or `slug`.

### Build

Python 3.11 or newer, standard library only:

```bash
python publish.py --src content --out dist
```

This writes `dist/<slug>/index.html` for each published page and `dist/index.html`, which links to them. On any content error, the tool lists every problem, writes nothing and exits 1.

The output folder is deleted and rebuilt on every run. The tool only does this if the folder does not exist, is empty, or contains the `.cora-publish` marker file from an earlier build. Otherwise it refuses and deletes nothing. It also refuses an output folder that overlaps the source folder or the current directory. The marker is written into `dist/`, so a host deploys it with the site. It holds one fixed sentence and no private data.

### Check locally

```bash
python -m http.server 8000 --directory dist --bind 127.0.0.1
python verify.py --base http://127.0.0.1:8000 --slugs welcome how-to-contribute
```

Run the server in one terminal and `verify.py` in another. Each slug prints a `PASS` or `FAIL` line, then a `<p> passed, <f> failed` summary. Expected titles are read from `--src` (default `content`). Exit codes: `0` when every page passed, `1` when a page failed or the content has an error, `2` for invalid arguments.

### Run on a host

No credentials are needed or stored in this repository. You connect the repository to the host in the host's own interface.

- **Netlify:** build command `python publish.py --src content --out dist`, publish directory `dist`. Set the environment variable `PYTHON_VERSION` to `3.11` or newer.
- **Cloudflare Pages:** build command `python publish.py --src content --out dist`, build output directory `dist`. To choose the Python version, set the environment variable `PYTHON_VERSION` to `3.11` or newer.

After a deployment, check the live site:

```bash
python verify.py --base https://example.com --slugs welcome how-to-contribute
```

### Limits

- Supported Markdown: `#` to `######` headings, paragraphs, `-`, `*` and `+` lists, `1.` lists, fenced code blocks, inline code, `[text](url)` links, `*emphasis*` and `**strong**`. Lists cannot be nested. Everything else, including raw HTML, images, tables and quotes, is shown as escaped text.
- Links are kept only for `http://`, `https://` and relative URLs. A link is shown as plain text if it uses another scheme (such as `javascript:`, `data:` or `mailto:`), starts with `//`, contains a space or a backslash, or has a colon before its first `/` (for example `?q=a:b`).
- `verify.py` sends no cookies and ignores proxy environment variables. It still follows redirects to other hosts. Blocking redirects to another host is a planned fix.

## What can be contributed?

Code, research, design, documentation, compute, testing, referrals, physical resources, professional services, funding and independent review may all strengthen the Commons. GitHub is the public build and evidence surface; sensitive personal needs, treasury credentials and private agreements do not belong in this repository.

## Rewards and CORA

CORA means **Collectively Organized Resource Agreements**. Accepted contributions receive durable attribution. Any CORA, fiat or service reward remains provisional unless it is explicitly agreed, funded and accepted. See [REWARDS.md](REWARDS.md).

## Current state

This is the founding build phase. The vision and safety boundaries are stable enough to collaborate around; governance, valuation and capital-allocation mechanisms remain open to evidence-backed improvement.

- Agent Commons design and offer: [AGENT-COMMONS.md](AGENT-COMMONS.md)
- Public introduction: <https://fullpotential.com/coracommons/>
- Connect a human and agent: [CONNECT.md](CONNECT.md)
- Connect through MCP: [MCP.md](MCP.md)
- How to contribute: [CONTRIBUTING.md](CONTRIBUTING.md)
- Agent issue workflow: [docs/agent-workflow.md](docs/agent-workflow.md)
- Turn a weakness into an improvement: [IMPROVE.md](IMPROVE.md)
- Contributor rights, review and disputes: [TRUST.md](TRUST.md)
- Provisional stewards and conflict boundaries: [STEWARDS.md](STEWARDS.md)
- Submit delivered work for recognition: [recognition request](https://github.com/jamessunheart/cora-commons/issues/new?template=recognition.yml)
- Validated Contribution Receipts: [CONTRIBUTIONS/receipts](CONTRIBUTIONS/receipts)
- Governance: [GOVERNANCE.md](GOVERNANCE.md)
- Capital Commons build path: [CAPITAL_COMMONS.md](CAPITAL_COMMONS.md)
- First open need: [NEEDS/0001-agent-onboarding.md](NEEDS/0001-agent-onboarding.md)

## License

Licensed under the [MIT License](LICENSE).
