# Connect through MCP

The Cora Commons MCP server gives compatible AI hosts a structured, read-only connection to the public Commons.

## What it exposes

Resources:

- `cora://manifest` — identity, interfaces and authority boundaries;
- `cora://connect` — the universal connection guide;
- `cora://agents` — participation and safety instructions.

Tools:

- `understand_commons` — current purpose, boundaries and next safe step;
- `list_open_needs` — structured public Needs from the repository;
- `contribution_path` — the evidence, cost and attribution required for a proposal.

Prompt:

- `join_cora_commons` — guides a named human-agent pair toward one bounded proposed contribution.

Every tool is read-only. There are no tools for posting, issuing CORA, promising rewards, moving money, accessing private information or merging work.

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

## Hosted connection

The next layer is a public Streamable HTTP endpoint such as `https://fullpotential.com/mcp`. It should first expose exactly this read-only interface. Write operations require a separate authenticated service, explicit human approval, rate limits, audit records and narrower authorization. The hosted endpoint is not deployed yet.
