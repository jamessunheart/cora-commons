"""Score an inbox triage result against labeled messages (issue #43).

The scorer reads only the ids in ``output["messages"]`` and their order. A label id
missing from the output counts as predicted noise. A message counts as high only
when its label is not noise and has priority "high". Scores, reasons and
``dropped_by_reason`` are ignored.

Precision@k divides by k even when fewer than k messages are kept or fewer than
k are labelled high, so the best possible score can be below 1.0; noise
precision is None when nothing is dropped and noise recall is None when nothing
is labelled noise. A label's ``noise_reason`` is informational and is not read
by the scorer.
"""

from __future__ import annotations

from typing import Any


TOP_K = (5, 10)
PRIORITIES = ("high", "medium", "low")


def _check_labels(labels: object) -> None:
    if not isinstance(labels, dict):
        raise ValueError("labels must be a dict")
    for label_id, label in labels.items():
        if not isinstance(label, dict):
            raise ValueError(f"label {label_id} must be a dict")
        noise = label.get("noise")
        if not isinstance(noise, bool):
            raise ValueError(f"label {label_id} must have a true or false noise flag")
        priority = label.get("priority")
        if noise and priority is not None and priority not in PRIORITIES:
            raise ValueError(f"noise label {label_id} must have priority None, high, medium or low")
        if not noise and priority not in PRIORITIES:
            raise ValueError(f"kept label {label_id} must have priority high, medium or low")


def _output_ids(output: object, labels: dict[str, Any]) -> list[str]:
    if not isinstance(output, dict):
        raise ValueError("output must be a dict")
    messages = output.get("messages")
    if not isinstance(messages, list):
        raise ValueError("output must have a 'messages' list")
    ids: list[str] = []
    seen: set[str] = set()
    for index, message in enumerate(messages):
        message_id = message.get("id") if isinstance(message, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise ValueError(f"message at index {index} has no text id")
        if message_id not in labels:
            raise ValueError(f"unknown id in output: {message_id}")
        if message_id in seen:
            raise ValueError(f"duplicate id in output: {message_id}")
        seen.add(message_id)
        ids.append(message_id)
    return ids


def _is_high(label: dict[str, Any]) -> bool:
    return label["noise"] is False and label["priority"] == "high"


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def score_triage(output: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    """Return noise precision/recall and precision@5/@10 for high-priority messages."""
    _check_labels(labels)
    ids = _output_ids(output, labels)
    predicted_noise = set(labels) - set(ids)
    actual_noise = {label_id for label_id, label in labels.items() if label["noise"]}
    true_positives = len(predicted_noise & actual_noise)
    high_in_top = {k: sum(1 for i in ids[:k] if _is_high(labels[i])) for k in TOP_K}
    result: dict[str, Any] = {
        "noise_precision": _ratio(true_positives, len(predicted_noise)),
        "noise_recall": _ratio(true_positives, len(actual_noise)),
    }
    result.update({f"precision_at_{k}": high_in_top[k] / k for k in TOP_K})
    result["counts"] = {
        "true_positives": true_positives,
        "false_positives": len(predicted_noise - actual_noise),
        "false_negatives": len(actual_noise - predicted_noise),
        **{f"high_in_top_{k}": high_in_top[k] for k in TOP_K},
    }
    return result
