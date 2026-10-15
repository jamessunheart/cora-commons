"""Deterministic access to the repository's public Commons records."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .receipts import RECEIPT_STATES, receipt_paths, validate_receipt


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DOCUMENTS = (
    "README.md",
    "VISION.md",
    "CAPITAL_COMMONS.md",
    "CONNECT.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "REWARDS.md",
    "MCP.md",
    "IMPROVE.md",
    "TRUST.md",
    "STEWARDS.md",
)
RECORD_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")
RECEIPT_STATE_RANK = {state: index for index, state in enumerate(RECEIPT_STATES)}


def read_text(relative_path: str) -> str:
    path = (REPO_ROOT / relative_path).resolve()
    if REPO_ROOT not in path.parents or not path.is_file():
        raise ValueError(f"Unknown public Commons document: {relative_path}")
    return path.read_text(encoding="utf-8")


def manifest() -> dict[str, object]:
    return json.loads(read_text("commons.json"))


def needs() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in sorted((REPO_ROOT / "NEEDS").glob("*.md")):
        if path.name == "README.md":
            continue
        body = path.read_text(encoding="utf-8")
        title = next(
            (line.removeprefix("# ").strip() for line in body.splitlines() if line.startswith("# ")),
            path.stem,
        )
        records.append(
            {
                "id": path.stem,
                "title": title,
                "repository_path": str(path.relative_to(REPO_ROOT)),
                "url": f"https://github.com/jamessunheart/cora-commons/blob/main/{path.relative_to(REPO_ROOT)}",
            }
        )
    return records


def need(need_id: str) -> dict[str, str]:
    if not RECORD_ID.fullmatch(need_id):
        raise ValueError("Invalid Need id")
    path = REPO_ROOT / "NEEDS" / f"{need_id}.md"
    if not path.is_file() or path.name == "README.md":
        raise ValueError(f"Unknown Need: {need_id}")
    body = path.read_text(encoding="utf-8")
    title = next(
        (line.removeprefix("# ").strip() for line in body.splitlines() if line.startswith("# ")),
        need_id,
    )
    return {
        "id": need_id,
        "title": title,
        "body": body,
        "repository_path": str(path.relative_to(REPO_ROOT)),
        "url": f"https://github.com/jamessunheart/cora-commons/blob/main/{path.relative_to(REPO_ROOT)}",
    }


def bricks() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in sorted((REPO_ROOT / "BRICKS").glob("*.md")):
        if path.name == "README.md":
            continue
        body = path.read_text(encoding="utf-8")
        title = next(
            (line.removeprefix("# ").strip() for line in body.splitlines() if line.startswith("# ")),
            path.stem,
        )
        records.append(
            {
                "id": path.stem,
                "title": title,
                "repository_path": str(path.relative_to(REPO_ROOT)),
                "url": f"https://github.com/jamessunheart/cora-commons/blob/main/{path.relative_to(REPO_ROOT)}",
            }
        )
    return records


def brick(brick_id: str) -> dict[str, str]:
    if not RECORD_ID.fullmatch(brick_id):
        raise ValueError("Invalid BRICK id")
    path = REPO_ROOT / "BRICKS" / f"{brick_id}.md"
    if not path.is_file() or path.name == "README.md":
        raise ValueError(f"Unknown BRICK: {brick_id}")
    body = path.read_text(encoding="utf-8")
    title = next(
        (line.removeprefix("# ").strip() for line in body.splitlines() if line.startswith("# ")),
        brick_id,
    )
    return {
        "id": brick_id,
        "title": title,
        "body": body,
        "repository_path": str(path.relative_to(REPO_ROOT)),
        "url": f"https://github.com/jamessunheart/cora-commons/blob/main/{path.relative_to(REPO_ROOT)}",
    }


def contribution_receipt(receipt_id: str) -> dict[str, object]:
    if not RECORD_ID.fullmatch(receipt_id):
        raise ValueError("Invalid Contribution Receipt id")
    path = REPO_ROOT / "CONTRIBUTIONS" / "receipts" / f"{receipt_id}.json"
    if not path.is_file():
        raise ValueError(f"Unknown Contribution Receipt: {receipt_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_receipt(data, path.name)
    if errors:
        raise ValueError(f"Invalid canonical Contribution Receipt {receipt_id}: {'; '.join(errors)}")
    return {
        **data,
        "repository_path": str(path.relative_to(REPO_ROOT)),
        "url": f"https://github.com/jamessunheart/cora-commons/blob/main/{path.relative_to(REPO_ROOT)}",
    }


def contribution_receipts() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in receipt_paths(REPO_ROOT):
        data = contribution_receipt(path.stem)
        records.append(
            {
                "receipt_id": data["receipt_id"],
                "status": data["status"],
                "need_id": data["need_id"],
                "contributors": data["contributors"],
                "artifact": data["artifact"],
                "review": data["review"],
                "reward": data["reward"],
                "url": data["url"],
            }
        )
    return records


def recognition_board() -> list[dict[str, object]]:
    totals: dict[str, dict[str, object]] = {}
    for receipt_record in contribution_receipts():
        status = str(receipt_record["status"])
        for contributor in receipt_record["contributors"]:
            contributor_id = str(contributor["id"])
            entry = totals.setdefault(
                contributor_id,
                {
                    "contributor_id": contributor_id,
                    "name": contributor["name"],
                    "kind": contributor["kind"],
                    "accepted_receipts": 0,
                    "reused_receipts": 0,
                    "impact_verified_receipts": 0,
                    "reward_allocated_receipts": 0,
                },
            )
            entry["accepted_receipts"] = int(entry["accepted_receipts"]) + 1
            if RECEIPT_STATE_RANK[status] >= RECEIPT_STATE_RANK["REUSED"]:
                entry["reused_receipts"] = int(entry["reused_receipts"]) + 1
            if RECEIPT_STATE_RANK[status] >= RECEIPT_STATE_RANK["IMPACT_VERIFIED"]:
                entry["impact_verified_receipts"] = int(entry["impact_verified_receipts"]) + 1
            if RECEIPT_STATE_RANK[status] >= RECEIPT_STATE_RANK["REWARD_ALLOCATED"]:
                entry["reward_allocated_receipts"] = int(entry["reward_allocated_receipts"]) + 1
    return sorted(
        totals.values(),
        key=lambda item: (-int(item["impact_verified_receipts"]), -int(item["reused_receipts"]), -int(item["accepted_receipts"]), str(item["contributor_id"])),
    )


def search(query: str, limit: int = 5) -> list[dict[str, object]]:
    tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9]+", query) if len(token) > 1}
    if not tokens:
        return []
    candidates = [REPO_ROOT / name for name in PUBLIC_DOCUMENTS]
    candidates.extend(sorted((REPO_ROOT / "NEEDS").glob("*.md")))
    candidates.extend(sorted((REPO_ROOT / "BRICKS").glob("*.md")))
    results: list[dict[str, object]] = []
    for path in candidates:
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        lowered = body.lower()
        matched = sorted(token for token in tokens if token in lowered)
        if not matched:
            continue
        first = min(lowered.find(token) for token in matched)
        start = max(0, first - 120)
        end = min(len(body), first + 360)
        excerpt = " ".join(body[start:end].split())
        results.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "matched_terms": matched,
                "score": len(matched),
                "excerpt": excerpt,
            }
        )
    results.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    return results[: max(1, min(limit, 20))]


def match_needs(capabilities: str, interests: str = "", limit: int = 3) -> list[dict[str, object]]:
    supplied = f"{capabilities} {interests}".strip()
    tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9]+", supplied) if len(token) > 2}
    matches: list[dict[str, object]] = []
    for record in needs():
        detail = need(record["id"])
        body = f"{detail['title']} {detail['body']}".lower()
        overlap = sorted(token for token in tokens if token in body)
        matches.append(
            {
                **record,
                "match_score": len(overlap),
                "matched_terms": overlap,
                "reason": (
                    f"Matched on: {', '.join(overlap)}" if overlap else "No direct keyword match; shown because it is an open founding Need."
                ),
            }
        )
    matches.sort(key=lambda item: (-int(item["match_score"]), str(item["id"])))
    return matches[: max(1, min(limit, 10))]


def pulse() -> dict[str, object]:
    receipt_records = contribution_receipts()
    accepted_bricks = bricks()
    return {
        "scope": "repository records available to this MCP server",
        "open_needs": len(needs()),
        "accepted_bricks": len(accepted_bricks),
        "contribution_receipts": len(receipt_records),
        "cora_calculated": None,
        "cora_available": None,
        "recognition_board": recognition_board(),
        "leaderboard": [],
        "cora_leaderboard": [],
        "evidence_note": "Recognition is derived only from validated, independently accepted Contribution Receipts. No CORA is inferred from commits, files or activity.",
    }


def overview() -> dict[str, object]:
    data = manifest()
    return {
        "name": data["name"],
        "description": data["description"],
        "loop": data["contribution_loop"],
        "default_agent_authority": data["default_agent_authority"],
        "requires_human_approval": data["requires_human_approval"],
        "not_live": data["not_live"],
        "acceptance_principle": data["acceptance_principle"],
        "capital_commons_phase": data["capital_commons_phase"],
        "priority_needs": data["priority_needs"],
        "next_step": "Review open needs. If you find a weakness, verify it and propose the smallest safe improvement; wait for human approval before posting or building.",
    }


def capital_build_path() -> dict[str, object]:
    data = manifest()
    return {
        "current_phase": data["capital_commons_phase"],
        "roadmap": data["capital_commons_roadmap"],
        "priority_needs": [need(need_id) for need_id in data["priority_needs"]],
        "ordered_phases": [
            "evidence foundation",
            "coordination foundation",
            "verified resource inventory",
            "economic simulation",
            "bounded funded or service-backed utility pilot",
            "authenticated allocation and federation",
        ],
        "first_proof": "A newcomer and their agent deliver useful work, receive durable attribution, pass independent review and create something another participant reuses.",
        "boundary": "Do not issue CORA, automate treasury actions or represent provisional calculations as available capital.",
    }
