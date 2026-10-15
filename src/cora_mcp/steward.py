"""Deterministic, draft-only triage for human-agent Commons activity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STEWARDSHIP_BOUNDARY = (
    "Draft-only triage. The Steward may classify, extract evidence, identify gaps "
    "and recommend routing. A human reviewer must decide acceptance; the Steward "
    "cannot issue CORA, spend funds, merge a receipt or resolve disputes."
)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _actor(payload: dict[str, Any], *paths: tuple[str, ...]) -> dict[str, str] | None:
    for path in paths:
        value: Any = payload
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, dict) and _text(value.get("login")):
            return {"id": value["login"], "name": value.get("name") or value["login"]}
    return None


def _body(payload: dict[str, Any]) -> str:
    issue = payload.get("issue") or payload.get("pull_request") or {}
    return "\n".join(
        part
        for part in (
            _text(payload.get("comment", {}).get("body")),
            _text(issue.get("title")),
            _text(issue.get("body")),
            _text(payload.get("pull_request", {}).get("body")),
        )
        if part
    )


def _evidence_body(payload: dict[str, Any], event_name: str) -> str:
    """Use the contributor-authored body for evidence, not surrounding issue text."""
    if event_name == "issue_comment":
        return _text(payload.get("comment", {}).get("body"))
    if event_name == "pull_request":
        return _text(payload.get("pull_request", {}).get("body"))
    issue = payload.get("issue") or {}
    return "\n".join(part for part in (_text(issue.get("title")), _text(issue.get("body"))) if part)


def _links(payload: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for key in ("html_url", "url"):
        for record in (payload, payload.get("issue", {}), payload.get("pull_request", {}), payload.get("comment", {})):
            value = record.get(key) if isinstance(record, dict) else None
            if isinstance(value, str) and value.startswith(("https://", "http://")) and value not in links:
                links.append(value)
    return links


def _missing(body: str, event_name: str) -> list[str]:
    lower = body.lower()
    required = {
        "a stated deliverable": ("deliverable", "delivered", "built", "implemented", "report"),
        "acceptance evidence": ("acceptance", "evidence", "test", "verified", "works", "reproduced"),
        "limitations or risks": ("limitation", "risk", "out of scope", "unknown"),
        "cost disclosure": ("cost", "hour", "minute", "compute", "ai"),
    }
    if event_name == "pull_request":
        required.pop("a stated deliverable", None)
    return [label for label, markers in required.items() if not any(marker in lower for marker in markers)]


def _event_name(event: dict[str, Any]) -> str:
    name = _text(event.get("event_name"))
    if name in {"issues", "issue_comment", "pull_request"}:
        return name
    if event.get("pull_request"):
        return "pull_request"
    if event.get("comment"):
        return "issue_comment"
    return "issues"


def review_event(event: dict[str, Any]) -> dict[str, Any]:
    """Create a bounded review packet from a GitHub event payload."""
    event_name = _event_name(event)
    issue = event.get("issue") or event.get("pull_request") or {}
    issue_number = issue.get("number") or event.get("number")
    author = _actor(event, ("comment", "user"), ("issue", "user"), ("pull_request", "user"), ("sender",))
    body = _body(event)
    evidence_body = _evidence_body(event, event_name)
    missing = _missing(evidence_body, event_name)
    labels = [label.get("name") for label in issue.get("labels", []) if isinstance(label, dict) and _text(label.get("name"))]
    contribution_signal = any(marker in evidence_body.lower() for marker in ("built", "implemented", "delivered", "report", "pull request", "proposal", "test"))
    if not author:
        status = "NEEDS_IDENTITY"
    elif not contribution_signal or missing:
        status = "NEEDS_INFO"
    else:
        status = "READY_FOR_REVIEW"
    return {
        "schema_version": "0.1",
        "steward_version": "0.1.0",
        "status": status,
        "event": {"name": event_name, "action": _text(event.get("action")) or None, "issue_number": issue_number, "labels": labels, "source_urls": _links(event)},
        "participants": {"observed_author": author, "human_and_agent_to_confirm": True, "instruction": "Do not infer an agent, operator, ownership or reward from a GitHub username alone."},
        "evidence": {
            "body_excerpt": body[:1600],
            "contribution_signal": contribution_signal,
            "missing_fields": missing,
            "claims_requiring_independent_check": [
                "the deliverable exists at the stated URL or commit",
                "the stated acceptance evidence is reproducible",
                "the human and agent attribution is accurate",
                "the disclosed cost and limitations are complete enough for this scope",
            ],
        },
        "routing": {
            "reviewer_status": "NOT_ASSIGNED",
            "reviewer_rule": "Choose a reviewer who is not listed as a contributor, did not author this event, and has no disclosed conflict of interest.",
            "next_action": "Ask for the missing fields before routing." if missing or not author else "Route to an independent reviewer and request an evidence decision.",
        },
        "receipt": {"status": "DRAFT_ONLY", "created": False, "reason": "A canonical receipt requires independent acceptance and a human-approved merge."},
        "authority_boundary": STEWARDSHIP_BOUNDARY,
    }


def markdown_summary(packet: dict[str, Any]) -> str:
    """Render a concise GitHub Actions job summary without claiming acceptance."""
    event = packet["event"]
    evidence = packet["evidence"]
    routing = packet["routing"]
    return "\n".join([
        "## Cora Steward review packet", "",
        f"**Status:** `{packet['status']}`",
        f"**Event:** `{event['name']}` #{event.get('issue_number') or 'unknown'}",
        f"**Observed author:** `{(packet['participants']['observed_author'] or {}).get('id', 'unknown')}`", "",
        "### Evidence check",
        f"- Contribution signal detected: `{evidence['contribution_signal']}`",
        f"- Missing fields: `{', '.join(evidence['missing_fields']) or 'none detected'}`",
        f"- Next action: {routing['next_action']}", "",
        "> This is draft-only triage. It is not acceptance, a Contribution Receipt, CORA issuance, funding, or a reward decision.", "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a draft-only Cora Steward review packet")
    parser.add_argument("event_path", type=Path)
    parser.add_argument("--output", type=Path, default=Path("steward-review.json"))
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    packet = review_event(json.loads(args.event_path.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.summary:
        args.summary.write_text(markdown_summary(packet), encoding="utf-8")
    print(json.dumps({"status": packet["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
