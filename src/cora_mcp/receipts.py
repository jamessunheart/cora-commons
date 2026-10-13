"""Deterministic validation for public Cora Commons Contribution Receipts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


RECEIPT_ID = re.compile(r"^CR-[A-Z0-9][A-Z0-9-]{2,63}$")
EVIDENCE_LEVELS = {"EXISTS", "RENDERS", "WORKS", "USABLE"}
RECEIPT_STATES = ("RECORDED", "ACCEPTED", "REUSED", "IMPACT_VERIFIED", "REWARD_ALLOCATED")
REWARD_STATES = {"RECOGNITION_ONLY", "PROVISIONAL", "FUNDED", "SERVICE_BACKED", "AVAILABLE", "SETTLED"}


def _is_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _required_string(record: dict[str, Any], field: str, errors: list[str], prefix: str = "") -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}{field} must be a non-empty string")
        return ""
    return value.strip()


def validate_receipt(data: object, filename: str | None = None) -> list[str]:
    """Return all validation errors; an empty list means the receipt is valid."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["receipt must be a JSON object"]

    if data.get("schema_version") != "0.1":
        errors.append("schema_version must be 0.1")

    receipt_id = _required_string(data, "receipt_id", errors)
    if receipt_id and not RECEIPT_ID.fullmatch(receipt_id):
        errors.append("receipt_id must match CR-[A-Z0-9-]")
    if filename and receipt_id and filename != f"{receipt_id}.json":
        errors.append(f"filename must be {receipt_id}.json")

    status = data.get("status")
    if status not in RECEIPT_STATES[1:]:
        errors.append("status must be ACCEPTED, REUSED, IMPACT_VERIFIED or REWARD_ALLOCATED")

    _required_string(data, "need_id", errors)
    _required_string(data, "agreement_url", errors)

    contributors = data.get("contributors")
    contributor_ids: set[str] = set()
    human_ids: set[str] = set()
    if not isinstance(contributors, list) or not contributors:
        errors.append("contributors must be a non-empty list")
    else:
        for index, contributor in enumerate(contributors):
            prefix = f"contributors[{index}]."
            if not isinstance(contributor, dict):
                errors.append(f"contributors[{index}] must be an object")
                continue
            contributor_id = _required_string(contributor, "id", errors, prefix)
            _required_string(contributor, "name", errors, prefix)
            _required_string(contributor, "role", errors, prefix)
            kind = contributor.get("kind")
            if kind not in {"human", "agent"}:
                errors.append(f"{prefix}kind must be human or agent")
            if contributor_id:
                if contributor_id in contributor_ids:
                    errors.append(f"duplicate contributor id: {contributor_id}")
                contributor_ids.add(contributor_id)
                if kind == "human":
                    human_ids.add(contributor_id)
            if kind == "agent":
                operator_id = _required_string(contributor, "operator_id", errors, prefix)
                _required_string(contributor, "authority", errors, prefix)
                if operator_id and operator_id not in contributor_ids and not any(
                    isinstance(item, dict) and item.get("id") == operator_id for item in contributors
                ):
                    errors.append(f"{prefix}operator_id must identify a listed contributor")
        if not human_ids:
            errors.append("at least one human contributor is required")

    artifact = data.get("artifact")
    if not isinstance(artifact, dict):
        errors.append("artifact must be an object")
    else:
        _required_string(artifact, "summary", errors, "artifact.")
        _required_string(artifact, "url", errors, "artifact.")
        _required_string(artifact, "version", errors, "artifact.")

    delivery = data.get("delivery")
    if not isinstance(delivery, dict):
        errors.append("delivery must be an object")
    else:
        if not _is_timestamp(delivery.get("delivered_at")):
            errors.append("delivery.delivered_at must be an ISO timestamp")
        limitations = delivery.get("limitations")
        if not isinstance(limitations, list) or not limitations or not all(
            isinstance(item, str) and item.strip() for item in limitations
        ):
            errors.append("delivery.limitations must be a non-empty string list")
        capital = delivery.get("capital_consumed")
        if not isinstance(capital, dict):
            errors.append("delivery.capital_consumed must be an object")
        else:
            hours = capital.get("human_hours")
            if hours is not None and (not isinstance(hours, (int, float)) or hours < 0):
                errors.append("delivery.capital_consumed.human_hours must be non-negative or null")
            _required_string(capital, "ai_compute", errors, "delivery.capital_consumed.")
            cash = capital.get("cash")
            if not isinstance(cash, dict):
                errors.append("delivery.capital_consumed.cash must be an object")
            else:
                amount = cash.get("amount")
                if amount is not None and (not isinstance(amount, (int, float)) or amount < 0):
                    errors.append("delivery.capital_consumed.cash.amount must be non-negative or null")
                _required_string(cash, "currency", errors, "delivery.capital_consumed.cash.")
                if cash.get("status") not in {"known", "estimated", "unknown"}:
                    errors.append("delivery.capital_consumed.cash.status must be known, estimated or unknown")

    review = data.get("review")
    if not isinstance(review, dict):
        errors.append("review must be an object")
    else:
        reviewer_id = _required_string(review, "reviewer_id", errors, "review.")
        _required_string(review, "reviewer_name", errors, "review.")
        if reviewer_id and reviewer_id in contributor_ids:
            errors.append("reviewer_id must not be a contributor id")
        if review.get("decision") != "ACCEPTED":
            errors.append("review.decision must be ACCEPTED before a receipt is merged")
        if review.get("evidence_level") not in EVIDENCE_LEVELS:
            errors.append("review.evidence_level must be EXISTS, RENDERS, WORKS or USABLE")
        if not _is_timestamp(review.get("reviewed_at")):
            errors.append("review.reviewed_at must be an ISO timestamp")
        evidence_urls = review.get("evidence_urls")
        if not isinstance(evidence_urls, list) or not evidence_urls or not all(
            isinstance(item, str) and item.strip() for item in evidence_urls
        ):
            errors.append("review.evidence_urls must be a non-empty string list")

    reward = data.get("reward")
    if not isinstance(reward, dict):
        errors.append("reward must be an object")
    else:
        reward_status = reward.get("status")
        if reward_status not in REWARD_STATES:
            errors.append("reward.status is invalid")
        cora_fields = ("cora_calculated", "cora_funded", "cora_available")
        for field in cora_fields:
            value = reward.get(field)
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                errors.append(f"reward.{field} must be non-negative or null")
        if reward_status == "RECOGNITION_ONLY" and any(reward.get(field) is not None for field in cora_fields):
            errors.append("recognition-only receipts cannot report calculated, funded or available CORA")
        if reward.get("cora_available") is not None and reward.get("cora_funded") is None:
            errors.append("CORA cannot be available without funded or service-backed capacity")

    events = data.get("events")
    if not isinstance(events, list) or len(events) < 2:
        errors.append("events must include at least RECORDED and ACCEPTED")
    else:
        seen_event_ids: set[str] = set()
        state_events: list[str] = []
        last_rank = -1
        for index, event in enumerate(events):
            prefix = f"events[{index}]."
            if not isinstance(event, dict):
                errors.append(f"events[{index}] must be an object")
                continue
            event_id = _required_string(event, "event_id", errors, prefix)
            if event_id in seen_event_ids:
                errors.append(f"duplicate event_id: {event_id}")
            seen_event_ids.add(event_id)
            event_type = event.get("type")
            if event_type not in RECEIPT_STATES:
                errors.append(f"{prefix}type is invalid")
            else:
                rank = RECEIPT_STATES.index(event_type)
                if rank < last_rank:
                    errors.append("receipt state events cannot move backwards")
                last_rank = rank
                state_events.append(event_type)
            _required_string(event, "actor", errors, prefix)
            if not _is_timestamp(event.get("at")):
                errors.append(f"{prefix}at must be an ISO timestamp")
        if state_events and state_events[0] != "RECORDED":
            errors.append("first state event must be RECORDED")
        if "ACCEPTED" not in state_events:
            errors.append("events must include ACCEPTED")
        if status in RECEIPT_STATES and state_events and state_events[-1] != status:
            errors.append("status must equal the latest state event")

    return errors


def load_receipt(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_path(path: Path) -> list[str]:
    try:
        data = load_receipt(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read valid JSON: {exc}"]
    return validate_receipt(data, path.name)


def receipt_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "CONTRIBUTIONS" / "receipts").glob("CR-*.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Cora Commons Contribution Receipts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("paths", nargs="+", type=Path)
    validate_all = subparsers.add_parser("validate-all")
    validate_all.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    paths = args.paths if args.command == "validate" else receipt_paths(args.repo_root.resolve())
    failed = False
    for path in paths:
        errors = validate_path(path)
        if errors:
            failed = True
            print(f"INVALID {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"VALID {path}")
    if not paths:
        print("VALID no canonical receipts yet")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
