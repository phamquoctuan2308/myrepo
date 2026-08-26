"""Deterministic scoring primitives shared by the live task-extraction benchmark and CI tests."""

from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from scripts.eval_data import ExpectedTask


def parse_predicted(raw: str) -> list[dict]:
    """Accept only the JSON-array contract emitted by ``extract_tasks``."""
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def check_date(predicted: dict, expected: ExpectedTask, today: date, timezone: ZoneInfo) -> bool | None:
    """Return date correctness, or ``None`` where the case deliberately has no precise date."""
    if expected.expected_date is None:
        return None
    raw_due = predicted.get("due_at")
    if not raw_due:
        return False
    try:
        parsed = datetime.fromisoformat(raw_due)
    except (TypeError, ValueError):
        return False
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone)
    if parsed.date() != expected.expected_date(today):
        return False
    if expected.expected_hour_range is not None:
        lo, hi = expected.expected_hour_range
        if not lo <= parsed.hour <= hi:
            return False
    return True


def score_case(
    expected: list[ExpectedTask], predicted: list[dict], today: date, timezone: ZoneInfo
) -> tuple[int, int, int, list[bool]]:
    """Score one conversation: task-title precision/recall and exact date correctness separately."""
    remaining = list(predicted)
    true_positives = 0
    date_results: list[bool] = []
    for expected_task in expected:
        match = next(
            (
                item
                for item in remaining
                if any(keyword.lower() in str(item.get("title", "")).lower() for keyword in expected_task.keywords)
            ),
            None,
        )
        if match is not None:
            remaining.remove(match)
            true_positives += 1
            date_ok = check_date(match, expected_task, today, timezone)
            if date_ok is not None:
                date_results.append(date_ok)
    return true_positives, len(remaining), len(expected) - true_positives, date_results
