"""Read-only MCP server for the public Cora Commons."""

from __future__ import annotations

import argparse

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from .catalog import brick, bricks, manifest, match_needs, need, needs, overview, pulse, read_text, search


mcp = MCPServer(
    "Cora Commons",
    version="0.3.0",
    website_url="https://fullpotential.com/coracommons/",
)

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True)


@mcp.resource("cora://manifest")
def commons_manifest() -> str:
    """Machine-readable identity, interfaces and authority boundaries."""
    return read_text("commons.json")


@mcp.resource("cora://connect")
def connection_guide() -> str:
    """Universal human-agent connection guide."""
    return read_text("CONNECT.md")


@mcp.resource("cora://agents")
def agent_instructions() -> str:
    """Safety and participation instructions for agents."""
    return read_text("AGENTS.md")


@mcp.resource("cora://needs/{need_id}")
def need_resource(need_id: str) -> str:
    """Read one public Need by its repository id."""
    return need(need_id)["body"]


@mcp.resource("cora://bricks/{brick_id}")
def brick_resource(brick_id: str) -> str:
    """Read one independently accepted BRICK by its repository id."""
    return brick(brick_id)["body"]


@mcp.tool(annotations=READ_ONLY)
def understand_commons() -> dict[str, object]:
    """Explain the current public Commons, authority boundaries and next safe step."""
    return overview()


@mcp.tool(annotations=READ_ONLY)
def list_open_needs() -> list[dict[str, str]]:
    """List repository Needs available for public exploration."""
    return needs()


@mcp.tool(annotations=READ_ONLY)
def get_need(need_id: str) -> dict[str, str]:
    """Read one public Need, including its outcome and acceptance evidence."""
    return need(need_id)


@mcp.tool(annotations=READ_ONLY)
def list_accepted_bricks() -> list[dict[str, str]]:
    """List independently accepted BRICKS; returns an empty list when none exist."""
    return bricks()


@mcp.tool(annotations=READ_ONLY)
def search_commons(query: str, limit: int = 5) -> list[dict[str, object]]:
    """Search canonical public Commons documents, Needs and accepted BRICKS."""
    return search(query, limit)


@mcp.tool(annotations=READ_ONLY)
def match_contribution(
    capabilities: str,
    interests: str = "",
    time_budget_hours: float | None = None,
    limit: int = 3,
) -> dict[str, object]:
    """Match stated capabilities to open Needs without claiming acceptance or reward."""
    return {
        "matches": match_needs(capabilities, interests, limit),
        "time_budget_hours": time_budget_hours,
        "method": "transparent keyword overlap over canonical open Need records",
        "next_step": "Choose one candidate, define a deliverable and acceptance evidence, then obtain human agreement before substantial work.",
    }


@mcp.tool(annotations=READ_ONLY)
def draft_contribution_proposal(
    need_id: str,
    human: str,
    agent: str,
    deliverable: str,
    acceptance_evidence: str,
    expected_cost: str,
    limitations: str,
    expected_return: str = "Recognition only unless separately agreed and funded",
) -> dict[str, object]:
    """Draft—but never post—a bounded contribution agreement for human approval."""
    selected = need(need_id)
    markdown = f"""# Contribution proposal — {selected['title']}

## Participants
- Human: {human}
- Agent: {agent}

## Deliverable
{deliverable}

## Acceptance evidence
{acceptance_evidence}

## Expected cost
{expected_cost}

## Limitations and out of scope
{limitations}

## Expected return
{expected_return}

## Authority boundary
This is a draft for human and reviewer agreement. It has not been posted, accepted, funded or rewarded.
"""
    return {
        "need": {"id": selected["id"], "title": selected["title"], "url": selected["url"]},
        "draft_markdown": markdown,
        "status": "draft_only",
        "requires_human_approval_before_posting": True,
    }


@mcp.tool(annotations=READ_ONLY)
def validate_contribution_proposal(
    need_id: str,
    human: str,
    agent: str,
    deliverable: str,
    acceptance_evidence: str,
    expected_cost: str,
    limitations: str,
) -> dict[str, object]:
    """Check whether a proposal has the minimum fields needed for agreement."""
    errors: list[str] = []
    try:
        need(need_id)
    except ValueError as exc:
        errors.append(str(exc))
    fields = {
        "human": human,
        "agent": agent,
        "deliverable": deliverable,
        "acceptance_evidence": acceptance_evidence,
        "expected_cost": expected_cost,
        "limitations": limitations,
    }
    for field, value in fields.items():
        if not value.strip():
            errors.append(f"Missing {field.replace('_', ' ')}")
    return {
        "complete": not errors,
        "errors": errors,
        "status": "ready_for_human_agreement" if not errors else "needs_revision",
        "boundary": "Completeness is not acceptance, verification, funding or authorization to post.",
    }


@mcp.tool(annotations=READ_ONLY)
def commons_pulse() -> dict[str, object]:
    """Return factual repository counts without inventing CORA or leaderboard value."""
    return pulse()


@mcp.tool(annotations=READ_ONLY)
def contribution_path() -> dict[str, object]:
    """Return the evidence-gated contribution path without taking external action."""
    data = manifest()
    return {
        "loop": data["contribution_loop"],
        "connection_guide": data["connection_guide"],
        "open_needs": data["open_needs"],
        "connection_check": data["connection_check"],
        "required_record": [
            "need addressed",
            "agreed scope",
            "deliverable",
            "acceptance evidence",
            "known and unknown cost",
            "dependencies",
            "limitations and risks",
            "human and agent attribution",
            "suggested next reuse",
        ],
        "boundary": "The MCP server is read-only. A human must approve any post, submission, spend, outreach or use of private information.",
    }


@mcp.prompt()
def join_cora_commons(human_name: str, contribution: str = "not yet known") -> str:
    """Prepare a safe first Cora Commons exploration for a human-agent pair."""
    return f"""You are assisting {human_name} in exploring Cora Commons.
Their possible contribution is: {contribution}.

Read cora://manifest, cora://connect and cora://agents. Then call understand_commons,
list_open_needs and contribution_path. Explain the Commons in five plain-language
sentences and recommend one small contribution with a deliverable, acceptance evidence,
estimated human/AI/compute cost, limitations and likely reuse. Wait for explicit human
approval before posting, submitting, spending, contacting anyone or using private data."""


def parse_args() -> argparse.Namespace:
    """Parse the small, explicit transport surface used locally and in production."""
    parser = argparse.ArgumentParser(description="Cora Commons MCP contribution copilot")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="stdio for a local host; streamable-http for the hosted endpoint",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8840)
    return parser.parse_args()


def main() -> None:
    """Run the local stdio server or the hardened, stateless HTTP service."""
    args = parse_args()
    if args.transport == "stdio":
        mcp.run()
        return

    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        max_request_body_size=256 * 1024,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                "fullpotential.com",
                "www.fullpotential.com",
                "127.0.0.1:*",
                "localhost:*",
            ],
            allowed_origins=[
                "https://fullpotential.com",
                "https://www.fullpotential.com",
            ],
        ),
    )


if __name__ == "__main__":
    main()
