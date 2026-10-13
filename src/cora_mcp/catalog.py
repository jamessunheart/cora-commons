"""Deterministic access to the repository's public Commons records."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


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
        "next_step": "Review open needs and propose one bounded contribution; wait for human approval before posting or building.",
    }
