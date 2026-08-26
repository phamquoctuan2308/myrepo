"""Validate anonymized user feedback and generate aggregate evaluation evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "eval" / "user_feedback" / "responses.csv"
DEFAULT_JSON = ROOT / "eval" / "results" / "user-feedback-latest.json"
DEFAULT_MD = ROOT / "eval" / "results" / "user-feedback-latest.md"
REQUIRED_FIELDS = {
    "response_id",
    "participant_id",
    "tested_at",
    "role",
    "scenario",
    "task_completed",
    "rating_1_5",
    "helpfulness_1_5",
    "trust_1_5",
    "would_use_again",
    "issue_category",
    "comment",
    "consent_to_use_anonymized_quote",
}


def parse_bool(value: str, *, field: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"Row {row_number}: {field} must be true or false")
    return normalized == "true"


def parse_rating(value: str, *, field: str, row_number: int) -> int:
    try:
        rating = int(value)
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: {field} must be an integer from 1 to 5") from exc
    if not 1 <= rating <= 5:
        raise ValueError(f"Row {row_number}: {field} must be from 1 to 5")
    return rating


def load_responses(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED_FIELDS - fields
        if missing:
            raise ValueError(f"Feedback CSV is missing columns: {', '.join(sorted(missing))}")
        responses: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            response_id = row["response_id"].strip()
            participant_id = row["participant_id"].strip()
            if not response_id or not participant_id or not row["scenario"].strip():
                raise ValueError(f"Row {row_number}: response_id, participant_id and scenario are required")
            if response_id in seen_ids:
                raise ValueError(f"Row {row_number}: duplicate response_id {response_id!r}")
            seen_ids.add(response_id)
            responses.append(
                {
                    "response_id": response_id,
                    "participant_id": participant_id,
                    "tested_at": row["tested_at"].strip(),
                    "role": row["role"].strip(),
                    "scenario": row["scenario"].strip(),
                    "task_completed": parse_bool(row["task_completed"], field="task_completed", row_number=row_number),
                    "rating": parse_rating(row["rating_1_5"], field="rating_1_5", row_number=row_number),
                    "helpfulness": parse_rating(row["helpfulness_1_5"], field="helpfulness_1_5", row_number=row_number),
                    "trust": parse_rating(row["trust_1_5"], field="trust_1_5", row_number=row_number),
                    "would_use_again": parse_bool(
                        row["would_use_again"], field="would_use_again", row_number=row_number
                    ),
                    "issue_category": row["issue_category"].strip() or "none",
                    "comment": row["comment"].strip(),
                    "quote_consent": parse_bool(
                        row["consent_to_use_anonymized_quote"],
                        field="consent_to_use_anonymized_quote",
                        row_number=row_number,
                    ),
                }
            )
    return responses


def summarize(responses: list[dict[str, Any]], minimum_participants: int) -> dict[str, Any]:
    participant_count = len({response["participant_id"] for response in responses})
    response_count = len(responses)
    if not responses:
        return {
            "status": "PENDING",
            "participant_count": 0,
            "response_count": 0,
            "minimum_participants": minimum_participants,
        }

    def average(field: str) -> float:
        return round(sum(response[field] for response in responses) / response_count, 3)

    status = "READY" if participant_count >= minimum_participants else "INSUFFICIENT_DATA"
    issue_counts = Counter(response["issue_category"] for response in responses)
    return {
        "status": status,
        "participant_count": participant_count,
        "response_count": response_count,
        "minimum_participants": minimum_participants,
        "task_completion_rate": round(sum(response["task_completed"] for response in responses) / response_count, 6),
        "rating_mean": average("rating"),
        "helpfulness_mean": average("helpfulness"),
        "trust_mean": average("trust"),
        "would_use_again_rate": round(sum(response["would_use_again"] for response in responses) / response_count, 6),
        "issue_categories": dict(sorted(issue_counts.items())),
        "consented_anonymized_quotes": [
            response["comment"] for response in responses if response["quote_consent"] and response["comment"]
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    if report["status"] == "PENDING":
        return f"""# User Feedback Evidence

- Status: **PENDING**
- Participants: `0/{report["minimum_participants"]}` minimum
- No rating has been invented. Add anonymized responses to `eval/user_feedback/responses.csv`.
"""
    return f"""# User Feedback Evidence

- Status: **{report["status"]}**
- Participants: `{report["participant_count"]}` (minimum `{report["minimum_participants"]}`)
- Responses: `{report["response_count"]}`

| Metric | Result |
|---|---:|
| Task completion | {report["task_completion_rate"] * 100:.1f}% |
| Overall rating | {report["rating_mean"]:.2f}/5 |
| Helpfulness | {report["helpfulness_mean"]:.2f}/5 |
| Trust | {report["trust_mean"]:.2f}/5 |
| Would use again | {report["would_use_again_rate"] * 100:.1f}% |
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--minimum-participants", type=int, default=5)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()
    try:
        responses = load_responses(args.input)
        report = summarize(responses, args.minimum_participants)
    except (OSError, ValueError) as exc:
        print(f"User feedback validation failed: {exc}", file=sys.stderr)
        return 2
    report["generated_at"] = datetime.now(UTC).isoformat()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0 if report["status"] in {"PENDING", "READY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
