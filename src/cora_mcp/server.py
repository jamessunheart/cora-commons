"""Read-only MCP server for the public Cora Commons."""

from __future__ import annotations

import argparse

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from .catalog import (
    brick,
    bricks,
    capital_build_path,
    contribution_receipt,
    contribution_receipts,
    manifest,
    match_needs,
    need,
    needs,
    overview,
    pulse,
    read_text,
    recognition_board,
    search,
)
from .steward import review_event


mcp = MCPServer(
    "Cora Commons",
    version="0.6.0",
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


@mcp.resource("cora://capital")
def capital_commons_roadmap() -> str:
    """Ordered build path from verified contributions to usable shared capital."""
    return read_text("CAPITAL_COMMONS.md")


@mcp.resource("cora://improve")
def improvement_guide() -> str:
    """Guide for converting a verified weakness into a bounded solution."""
    return read_text("IMPROVE.md")


@mcp.resource("cora://trust")
def trust_policy() -> str:
    """Current contributor-rights, independent-review and dispute boundary."""
    return read_text("TRUST.md")


@mcp.resource("cora://stewards")
def stewards_policy() -> str:
    """Current provisional steward appointments and conflict boundaries."""
    return read_text("STEWARDS.md")


@mcp.resource("cora://needs/{need_id}")
def need_resource(need_id: str) -> str:
    """Read one public Need by its repository id."""
    return need(need_id)["body"]


@mcp.resource("cora://bricks/{brick_id}")
def brick_resource(brick_id: str) -> str:
    """Read one independently accepted BRICK by its repository id."""
    return brick(brick_id)["body"]


@mcp.resource("cora://receipts/{receipt_id}")
def receipt_resource(receipt_id: str) -> str:
    """Read one validated, independently accepted Contribution Receipt."""
    import json

    return json.dumps(contribution_receipt(receipt_id), indent=2, sort_keys=True)


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


@mcp.tool(annotations=READ_ONLY)
def improvement_path(
    weakness: str,
    human: str,
    agent: str,
    desired_outcome: str,
    smallest_solution: str,
    acceptance_evidence: str,
    expected_cost_and_risks: str,
    existing_work_checked: str = "Not yet checked",
) -> dict[str, object]:
    """Turn a weakness into an unposted, human-approved improvement draft."""
    fields = {
        "weakness": weakness,
        "human": human,
        "agent": agent,
        "desired_outcome": desired_outcome,
        "smallest_solution": smallest_solution,
        "acceptance_evidence": acceptance_evidence,
        "expected_cost_and_risks": expected_cost_and_risks,
    }
    missing = [name.replace("_", " ") for name, value in fields.items() if not value.strip()]
    draft = f"""# Improvement proposal

## Verified weakness
{weakness}

## Existing work checked
{existing_work_checked}

## Desired outcome
{desired_outcome}

## Smallest safe solution
{smallest_solution}

## Acceptance evidence
{acceptance_evidence}

## Cost, dependencies, rights and risks
{expected_cost_and_risks}

## Attribution and authority
- Human: {human}
- Agent: {agent}
- Authority: draft only; human approval required before posting or building
"""
    return {
        "complete": not missing,
        "missing": missing,
        "draft_markdown": draft,
        "status": "draft_only",
        "submit": manifest()["improvement_submission"],
        "next_step": "Search current Needs and issues, then ask the directing human whether to post this draft or revise it.",
        "boundary": "Finding a weakness and drafting a solution are not authority to post, build, accept, fund or reward it.",
    }


@mcp.tool(annotations=READ_ONLY)
def capital_commons_build_path() -> dict[str, object]:
    """Return the ordered Capital Commons phases and current priority Needs."""
    return capital_build_path()


@mcp.tool(annotations=READ_ONLY)
def list_contribution_receipts() -> list[dict[str, object]]:
    """List validated, independently accepted Contribution Receipts."""
    return contribution_receipts()


@mcp.tool(annotations=READ_ONLY)
def get_contribution_receipt(receipt_id: str) -> dict[str, object]:
    """Read one canonical Contribution Receipt and its evidence/reward boundary."""
    return contribution_receipt(receipt_id)


@mcp.tool(annotations=READ_ONLY)
def commons_recognition() -> dict[str, object]:
    """Show evidence-based recognition without inventing CORA value."""
    return {
        "contributors": recognition_board(),
        "source": "validated canonical Contribution Receipts only",
        "excluded": ["connection activity", "commits without an accepted receipt", "self-claims", "unverified work"],
        "boundary": "Recognition is not CORA issuance, funding, ownership or a promise of payment.",
    }


@mcp.tool(annotations=READ_ONLY)
def recognition_path() -> dict[str, object]:
    """Explain how delivered work becomes durable public recognition."""
    data = manifest()
    return {
        "steps": [
            "agree scope and evidence before substantial work",
            "deliver an immutable artifact with cost and limitations",
            "submit a public recognition request",
            "receive independent review",
            "merge a validator-approved Contribution Receipt",
            "append later reuse, impact or reward evidence without rewriting history",
        ],
        "submit": data["recognition_submission"],
        "ledger": data["contribution_receipts"],
        "boundary": "Connection, conversation, commits and self-claims alone do not create recognized contribution credit.",
    }


@mcp.tool(annotations=READ_ONLY)
def steward_review_event(event: dict[str, object]) -> dict[str, object]:
    """Create a draft-only evidence and routing packet from a GitHub event."""
    return review_event(event)


@mcp.prompt()
def join_cora_commons(human_name: str, contribution: str = "not yet known") -> str:
    """Prepare a safe first Cora Commons exploration for a human-agent pair."""
    return f"""You are assisting {human_name} in exploring Cora Commons.
Their possible contribution is: {contribution}.

Read cora://manifest, cora://connect, cora://agents, cora://capital, cora://improve,
cora://trust and cora://stewards. Then call understand_commons, list_open_needs, contribution_path,
improvement_path when you find a material weakness, recognition_path and
capital_commons_build_path.
Explain the Commons in five plain-language
sentences and recommend one small contribution with a deliverable, acceptance evidence,
estimated human/AI/compute cost, limitations and likely reuse. Wait for explicit human
approval before posting, submitting, building, spending, contacting anyone or using private data."""


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
