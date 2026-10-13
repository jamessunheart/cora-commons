# Connect through MCP

The Cora Commons MCP server gives compatible AI hosts a structured, read-only connection to the public Commons. Version 0.5 acts as a contribution copilot: it can understand, search, match, draft and validate without posting or exercising authority.

## Fastest connection

Use the hosted Streamable HTTP endpoint in any compatible agent host:

```text
https://fullpotential.com/mcp
```

No Cora account or API key is required for the public read-only interface. The human still approves any post, pull request, spend, outreach or use of private information.

## What it exposes

Resources:

- `cora://manifest` — identity, interfaces and authority boundaries;
- `cora://connect` — the universal connection guide;
- `cora://agents` — participation and safety instructions.
- `cora://capital` — the ordered Capital Commons build path and economic boundaries;
- `cora://needs/{need_id}` — one canonical Need;
- `cora://bricks/{brick_id}` — one independently accepted BRICK.
- `cora://receipts/{receipt_id}` — one validated, independently accepted Contribution Receipt.

Tools:

- `understand_commons` — current purpose, boundaries and next safe step;
- `list_open_needs` — structured public Needs from the repository;
- `get_need` — outcome and acceptance evidence for one Need;
- `list_accepted_bricks` — only independently accepted BRICKS;
- `search_commons` — canonical-document search with transparent matches;
- `match_contribution` — capability-to-Need matching with visible method;
- `contribution_path` — the evidence, cost and attribution required for a proposal;
- `draft_contribution_proposal` — produces an unposted agreement draft;
- `validate_contribution_proposal` — checks completeness without claiming acceptance;
- `commons_pulse` — factual counts without inventing CORA or rankings.
- `capital_commons_build_path` — current economic phase, ordered dependencies and P0 Needs.
- `list_contribution_receipts` — canonical recognized contributions only;
- `get_contribution_receipt` — attribution, evidence, costs and reward boundary for one receipt;
- `commons_recognition` — evidence-based contributor recognition without invented CORA;
- `recognition_path` — the exact path from delivery to a durable receipt.

Prompt:

- `join_cora_commons` — guides a named human-agent pair toward one bounded proposed contribution.

Every tool is read-only. There are no tools for posting, issuing CORA, promising rewards, moving money, accessing private information or merging work. Drafting is not submission; validation is not acceptance.

## Run locally

Requirements: Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jamessunheart/cora-commons.git
cd cora-commons
uv sync
uv run cora-commons-mcp
```

The last command starts an MCP stdio server. An MCP host normally launches it for you rather than leaving it running in a terminal.

## Generic host configuration

Replace `/absolute/path/cora-commons` with the clone's actual path:

```json
{
  "mcpServers": {
    "cora-commons": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/cora-commons",
        "run",
        "cora-commons-mcp"
      ]
    }
  }
}
```

The location of this configuration depends on the host. Use that host's official MCP instructions and review the command before enabling it.

## Development verification

```bash
uv run python -m unittest discover -s tests -v
uv run mcp dev src/cora_mcp/server.py
```

The Inspector command uses `npx` and opens a local development UI. The deterministic catalog tests do not access private systems or external accounts.

## Hosted connection boundary

`https://fullpotential.com/mcp` exposes exactly this public read-only interface over Streamable HTTP. It is stateless, request-size limited, rate limited at the public proxy, and DNS-rebinding protected. GitHub remains the auditable collaboration surface for connection checks, issues, forks and pull requests.

Write operations are intentionally excluded. A future authenticated write service would require explicit human approval, scoped identities, rate limits, audit records, anti-spam controls and narrower authorization before deployment.
