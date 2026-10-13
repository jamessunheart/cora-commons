"""Read-only MCP server for the public Cora Commons."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .catalog import manifest, needs, overview, read_text


mcp = MCPServer(
    "Cora Commons",
    version="0.1.0",
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


@mcp.tool(annotations=READ_ONLY)
def understand_commons() -> dict[str, object]:
    """Explain the current public Commons, authority boundaries and next safe step."""
    return overview()


@mcp.tool(annotations=READ_ONLY)
def list_open_needs() -> list[dict[str, str]]:
    """List repository Needs available for public exploration."""
    return needs()


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


def main() -> None:
    """Run the local stdio transport used by MCP-capable agent hosts."""
    mcp.run()


if __name__ == "__main__":
    main()
