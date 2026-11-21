"""Deterministic tripwires that turn status signals into proposed actions."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


FUEL_THRESHOLD_PCT = 80
FUEL_CUTOFF_UTC = time(18, 0)
CHURN_REPEATS = 2
CLUSTER_MIN_TASKS = 3
STALL_GRACE_MULTIPLIER = 3
ORDER_TOP = 5
PROMISE_MAX_HOURS = 48
FOUNDATION_TAG = "foundation"


@dataclass(frozen=True)
class Action:
    kind: str
    target: str | None
    reason: str


def _number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isinstance(value, int) or math.isfinite(value)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: object) -> datetime | None:
    """Parse an ISO 8601 timestamp as UTC; naive values are treated as UTC."""
    if not isinstance(value, str) or not value:
        return None
    if value[-1] in "Zz":
        value = value[:-1] + "+00:00"
    try:
        return _utc(datetime.fromisoformat(value))
    except (ValueError, OverflowError):
        return None


def _param(rule: dict[str, Any], name: str, default: float) -> float:
    value = rule.get(name, default)
    if not _number(value):
        raise ValueError(f"{rule['type']} rule {name} must be a number")
    return value


def _items(state: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = state.get(field)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _task_id(value: object) -> str | None:
    """Accept a non-empty string or an integer (not a bool) as a task id, as text."""
    if _text(value):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _identified_tasks(state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    identified = ((_task_id(task.get("id")), task) for task in _items(state, "tasks"))
    return [(task_id, task) for task_id, task in identified if task_id is not None]


def _blocked_reasons(task: dict[str, Any]) -> list[str]:
    reasons = task.get("blocked_reasons")
    if not isinstance(reasons, list):
        return []
    return [reason for reason in reasons if _text(reason)]


def _fuel(state: dict[str, Any], rule: dict[str, Any], now: datetime) -> list[Action]:
    threshold = _param(rule, "threshold", FUEL_THRESHOLD_PCT)
    fuel = state.get("fuel_pct")
    if not _number(fuel) or fuel < threshold or now.time() >= FUEL_CUTOFF_UTC:
        return []
    return [Action("pause_non_foundation", None, f"fuel_pct {fuel} >= {threshold} before 18:00 UTC")]


def _churn(state: dict[str, Any], rule: dict[str, Any], now: datetime) -> list[Action]:
    repeats = _param(rule, "repeats", CHURN_REPEATS)
    actions: list[Action] = []
    for task_id, task in _identified_tasks(state):
        counts = Counter(_blocked_reasons(task))
        repeated = sorted(reason for reason, count in counts.items() if count >= repeats)
        if repeated:
            detail = "; ".join(f"{reason} x{counts[reason]}" for reason in repeated)
            actions.append(Action("park", task_id, f"blocked repeatedly by the same reason: {detail}"))
    return actions


def _cluster(state: dict[str, Any], rule: dict[str, Any], now: datetime) -> list[Action]:
    min_tasks = _param(rule, "min_tasks", CLUSTER_MIN_TASKS)
    tasks_by_blocker: dict[str, set[str]] = {}
    for task_id, task in _identified_tasks(state):
        for reason in _blocked_reasons(task):
            tasks_by_blocker.setdefault(reason, set()).add(task_id)
    return [
        Action("ensure_foundation", blocker, f"blocks {len(task_ids)} tasks: {', '.join(sorted(task_ids))}")
        for blocker, task_ids in sorted(tasks_by_blocker.items())
        if len(task_ids) >= min_tasks
    ]


def _stall(state: dict[str, Any], rule: dict[str, Any], now: datetime) -> list[Action]:
    multiplier = _param(rule, "multiplier", STALL_GRACE_MULTIPLIER)
    actions: list[Action] = []
    for worker in _items(state, "workers"):
        name = worker.get("name")
        minutes = worker.get("minutes_since_write")
        grace = worker.get("grace_minutes")
        if not _text(name) or not _number(minutes) or not _number(grace) or minutes < 0 or grace < 0:
            continue
        if minutes > multiplier * grace:
            reason = f"no write for {minutes} minutes > {multiplier} x grace of {grace} minutes"
            actions.append(Action("restart", name, reason))
    return actions


def _order(state: dict[str, Any], rule: dict[str, Any], now: datetime) -> list[Action]:
    top = _param(rule, "top", ORDER_TOP)
    ranked = sorted(
        ((task_id, task) for task_id, task in _identified_tasks(state) if _number(task.get("sort_order"))),
        key=lambda pair: (pair[1]["sort_order"], pair[0]),
    )
    actions: list[Action] = []
    for position, (task_id, task) in enumerate(ranked, start=1):
        tags = task.get("tags")
        if position > top and isinstance(tags, list) and FOUNDATION_TAG in tags:
            reason = f"tagged {FOUNDATION_TAG} but ranked {position} by sort_order, outside the top {top}"
            actions.append(Action("promote", task_id, reason))
    return actions


def _promise(state: dict[str, Any], rule: dict[str, Any], now: datetime) -> list[Action]:
    max_hours = _param(rule, "hours", PROMISE_MAX_HOURS)
    actions: list[Action] = []
    for commitment in _items(state, "commitments"):
        commitment_id = commitment.get("id")
        field = "last_moved"
        since = _parse_timestamp(commitment.get(field))
        if since is None:
            field = "opened"
            since = _parse_timestamp(commitment.get(field))
        if not _text(commitment_id) or since is None:
            continue
        if now - since > timedelta(hours=max_hours):
            reason = f"no movement since {field} {commitment[field]}, more than {max_hours}h"
            actions.append(Action("flag_red", commitment_id, reason))
    return actions


RULE_TYPES = ("fuel", "churn", "cluster", "stall", "order", "promise")
HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any], datetime], list[Action]]] = {
    "fuel": _fuel,
    "churn": _churn,
    "cluster": _cluster,
    "stall": _stall,
    "order": _order,
    "promise": _promise,
}
DEFAULT_RULES: list[dict[str, Any]] = [{"type": rule_type} for rule_type in RULE_TYPES]


def evaluate(state: dict[str, Any], rules: list[dict[str, Any]], now: datetime) -> list[Action]:
    """Return the actions the listed rules trigger, in rule order, then sorted by target and reason."""
    if not isinstance(state, dict):
        raise ValueError("state must be a JSON object")
    current = _utc(now)
    actions: list[Action] = []
    for rule in rules:
        rule_type = rule.get("type") if isinstance(rule, dict) else None
        if not isinstance(rule_type, str) or rule_type not in HANDLERS:
            raise ValueError(f"unknown rule type: {rule_type!r}")
        triggered = HANDLERS[rule_type](state, rule, current)
        actions.extend(sorted(triggered, key=lambda action: (action.target or "", action.reason)))
    return actions


def _now_argument(value: str) -> datetime:
    parsed = _parse_timestamp(value)
    if parsed is None:
        raise argparse.ArgumentTypeError("must be an ISO 8601 timestamp, for example 2026-11-21T10:00:00Z")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Cora tripwires against a status snapshot")
    parser.add_argument("--state", type=Path, required=True, help="status snapshot JSON file")
    parser.add_argument("--now", type=_now_argument, help="evaluation time, ISO 8601 UTC (default: current UTC time)")
    args = parser.parse_args()
    try:
        state = json.loads(args.state.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"cannot read valid JSON from {args.state}: {exc}")
    if not isinstance(state, dict):
        parser.error(f"{args.state} must contain a JSON object")

    now = args.now if args.now is not None else datetime.now(timezone.utc)
    lines = "".join(json.dumps(asdict(action), sort_keys=True) + "\n" for action in evaluate(state, DEFAULT_RULES, now))
    sys.stdout.buffer.write(lines.encode("utf-8"))


if __name__ == "__main__":
    main()
