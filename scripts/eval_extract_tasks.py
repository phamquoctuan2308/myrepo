"""Accuracy eval for the `extract_tasks` agent tool against a small hand-labeled dataset.

Calls the real LLM configured in `.env` (GOOGLE_API_KEY/GROQ_API_KEY + LLM_PROVIDER) - this
is a manual dev tool, not part of `pytest tests/` (CI has no real API key), and it costs real
tokens/quota to run. Use it to sanity-check accuracy after changing the extraction prompt or
swapping models/providers.

Scores two separate things, because they fail independently:
  - Title extraction (precision/recall/F1) - did it find the right item at all.
  - Date accuracy - for items with a date/time in the conversation, did it resolve relative
    dates ("tomorrow", "this Friday") against the *actual* current date. This is the ràng
    buộc đề bài cares about most directly ("giảm false reminder") and title P/R/F1 alone
    doesn't catch it - a task can have a perfect title and a wrong year.

Usage:
    python scripts/eval_extract_tasks.py
"""
import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Titles are Vietnamese; Windows consoles often default to a codepage (cp1252) that can't
# encode them, which crashes plain print() - force UTF-8 stdout regardless of platform default.
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.task_eval_metrics import parse_predicted, score_case  # noqa: E402
from src.agents.tools.task_tool import extract_tasks  # noqa: E402
from src.config import get_settings  # noqa: E402

F1_THRESHOLD = 0.7
DATE_ACCURACY_THRESHOLD = 0.7


def _next_weekday(base: date, weekday: int) -> date:
    """Next occurrence of `weekday` (0=Monday..6=Sunday) on/after `base` - today counts as
    "this Friday" if today already is Friday, matching how people actually mean it."""
    return base + timedelta(days=(weekday - base.weekday()) % 7)


@dataclass
class ExpectedTask:
    # Case-insensitive substrings expected in a predicted task's title - any one matching counts,
    # since extract_tasks always titles in Vietnamese and there's more than one valid phrasing.
    keywords: tuple[str, ...]
    # Expected calendar date, resolved against the actual "today" at eval time (not hardcoded -
    # the dataset uses relative phrases like "tomorrow"/"this Friday", same as real conversations
    # would). None means this item isn't expected to carry a date at all.
    expected_date: Callable[[date], date] | None = None
    # Optional expected hour-of-day range (inclusive) for items with an explicit time-of-day
    # mentioned, e.g. "3h chiều" (3pm) -> (14, 16). None skips the hour check.
    expected_hour_range: tuple[int, int] | None = None


@dataclass
class EvalCase:
    name: str
    conversation: str
    expected: list[ExpectedTask] = field(default_factory=list)


DATASET: list[EvalCase] = [
    EvalCase(
        name="single_task_explicit_weekday",
        conversation="Alice: Nhớ gửi báo cáo doanh thu cho sếp trước thứ Sáu này nhé.\nBob: ok để mình làm.",
        expected=[ExpectedTask(keywords=("báo cáo",), expected_date=lambda today: _next_weekday(today, 4))],
    ),
    EvalCase(
        name="single_task_relative_date",
        conversation="Bob: Can you review the PR by tomorrow morning? It's blocking the release.",
        expected=[ExpectedTask(keywords=("PR",), expected_date=lambda today: today + timedelta(days=1))],
    ),
    EvalCase(
        name="multiple_tasks_one_message",
        conversation=(
            "Manager: Team, before Friday please: 1) send me the Q3 budget draft, "
            "2) book the venue for the offsite, 3) confirm catering headcount."
        ),
        expected=[
            # extract_tasks always titles in Vietnamese (see task_tool.py's prompt), even for an
            # English conversation - accept a few plausible translations, not just one exact phrasing.
            ExpectedTask(keywords=("ngân sách", "budget"), expected_date=lambda today: _next_weekday(today, 4)),
            ExpectedTask(
                keywords=("địa điểm", "phòng", "venue", "offsite"),
                expected_date=lambda today: _next_weekday(today, 4),
            ),
            ExpectedTask(
                keywords=("khách", "catering", "ăn uống"), expected_date=lambda today: _next_weekday(today, 4)
            ),
        ],
    ),
    EvalCase(
        name="appointment_not_just_task",
        conversation="Chị ơi 3h chiều mai mình có hẹn khám răng, nhớ nhắc em nhé.",
        expected=[
            ExpectedTask(
                keywords=("khám răng",),
                expected_date=lambda today: today + timedelta(days=1),
                expected_hour_range=(14, 16),
            )
        ],
    ),
    EvalCase(
        name="task_buried_in_small_talk",
        conversation=(
            "Alice: haha đúng là vậy đó\n"
            "Bob: đúng rồi, à mà quên, mai deadline nộp đề cương dự án rồi đó\n"
            "Alice: ừ biết rồi, cảm ơn nhắc"
        ),
        expected=[ExpectedTask(keywords=("đề cương",), expected_date=lambda today: today + timedelta(days=1))],
    ),
    EvalCase(
        name="no_task_casual_chat",
        conversation="Bob: haha đúng rồi\nAlice: :)) vui thế\nBob: hôm nay trời đẹp ghê",
        expected=[],
    ),
    EvalCase(
        name="no_task_past_tense_recap",
        conversation="Alice: Hôm qua mình đã gửi báo cáo rồi, sếp đã duyệt xong.",
        expected=[],
    ),
    EvalCase(
        name="question_is_not_a_task",
        conversation="Bob: What time does the meeting usually start on Mondays?",
        expected=[],
    ),
    EvalCase(
        name="negated_request_is_not_a_task",
        conversation="Alice: Đừng gửi bản nháp hôm nay nhé, mình đã tự xử lý xong rồi.",
        expected=[],
    ),
    EvalCase(
        name="next_week_vietnamese",
        conversation="Nam: Thứ Hai tuần sau gửi mình kế hoạch sprint nhé.",
        expected=[ExpectedTask(keywords=("kế hoạch", "sprint"))],
    ),
    EvalCase(
        name="code_switched_deadline",
        conversation="Mai: Please chốt danh sách khách trước 5pm tomorrow giúp mình.",
        expected=[
            ExpectedTask(
                keywords=("danh sách", "khách"),
                expected_date=lambda today: today + timedelta(days=1),
                expected_hour_range=(16, 18),
            )
        ],
    ),
    EvalCase(
        name="completed_then_new_follow_up",
        conversation=(
            "An: Báo cáo tháng trước mình gửi xong rồi.\nBình: Tốt, vậy mai gửi thêm bản tóm tắt một trang nhé."
        ),
        expected=[ExpectedTask(keywords=("tóm tắt",), expected_date=lambda today: today + timedelta(days=1))],
    ),
    EvalCase(
        name="two_speakers_two_tasks",
        conversation=("Lan: Minh review PR trước thứ Sáu nhé.\nMinh: Ok, Lan nhớ đặt phòng họp cho buổi demo nữa."),
        expected=[ExpectedTask(keywords=("PR",)), ExpectedTask(keywords=("phòng", "demo"))],
    ),
]


def _parse_predicted(raw: str) -> list[dict]:
    return parse_predicted(raw)


def _score_case(
    expected: list[ExpectedTask], predicted: list[dict], today: date, tz: ZoneInfo
) -> tuple[int, int, int, list[bool]]:
    return score_case(expected, predicted, today, tz)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate real-LLM task extraction against the versioned dataset.")
    parser.add_argument("--as-of", help="Reference date in YYYY-MM-DD, for reproducible relative-date scoring.")
    parser.add_argument("--output", help="Optional UTF-8 JSON report path.")
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries per transient model-provider error before recording the case as failed (default: 2).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=45.0,
        help="Maximum seconds for one model call before retrying it (default: 45).",
    )
    return parser.parse_args()


async def main() -> None:
    args = _arguments()
    if args.retries < 0 or args.timeout_seconds <= 0:
        raise SystemExit("--retries must be non-negative and --timeout-seconds must be positive.")
    settings = get_settings()
    tz = ZoneInfo(settings.calendar_timezone)
    today = date.fromisoformat(args.as_of) if args.as_of else datetime.now(tz).date()

    total_tp = total_fp = total_fn = 0
    total_date_correct = total_date_checked = 0
    llm_errors: list[dict[str, str]] = []
    print(
        f"Running task-extraction accuracy eval on {len(DATASET)} cases (today = {today}, {settings.calendar_timezone})...\n"
    )

    for case in DATASET:
        raw = "[]"
        for attempt in range(args.retries + 1):
            try:
                raw = await asyncio.wait_for(
                    extract_tasks.coroutine(state={"context": case.conversation}),
                    timeout=args.timeout_seconds,
                )
                break
            except Exception as exc:  # noqa: BLE001 - report provider failure as evaluation evidence
                if attempt == args.retries:
                    llm_errors.append({"case": case.name, "error": f"{type(exc).__name__}: {exc}"})
                    print(f"[ERROR] {case.name}: model call failed after {attempt + 1} attempts")
                else:
                    await asyncio.sleep(attempt + 1)
        predicted = _parse_predicted(raw)
        tp, fp, fn, date_results = _score_case(case.expected, predicted, today, tz)
        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_date_correct += sum(date_results)
        total_date_checked += len(date_results)

        title_ok = fp == 0 and fn == 0
        dates_ok = all(date_results)
        status = "OK  " if title_ok and dates_ok else "MISS"
        date_summary = f" dates={sum(date_results)}/{len(date_results)}" if date_results else ""
        print(
            f"[{status}] {case.name}: expected={len(case.expected)} predicted={len(predicted)} "
            f"tp={tp} fp={fp} fn={fn}{date_summary}"
        )
        if fp or fn or not dates_ok:
            print(f"       predicted: {[(p.get('title'), p.get('due_at')) for p in predicted]}")

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 1.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    date_accuracy = total_date_correct / total_date_checked if total_date_checked else 1.0

    print(f"\nTitle extraction — Precision: {precision:.1%}  Recall: {recall:.1%}  F1: {f1:.1%}")
    print(f"Date accuracy — {total_date_correct}/{total_date_checked} correct ({date_accuracy:.1%})")

    if args.output:
        report_path = Path(args.output)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "as_of": today.isoformat(),
                    "timezone": settings.calendar_timezone,
                    "case_count": len(DATASET),
                    "title_precision": precision,
                    "title_recall": recall,
                    "title_f1": f1,
                    "date_correct": total_date_correct,
                    "date_checked": total_date_checked,
                    "date_accuracy": date_accuracy,
                    "f1_threshold": F1_THRESHOLD,
                    "date_accuracy_threshold": DATE_ACCURACY_THRESHOLD,
                    "request_timeout_seconds": args.timeout_seconds,
                    "llm_errors": llm_errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"JSON report written to {report_path}")

    failed = False
    if f1 < F1_THRESHOLD:
        print(f"Below {F1_THRESHOLD:.0%} F1 threshold - review the extraction prompt/model.")
        failed = True
    if date_accuracy < DATE_ACCURACY_THRESHOLD:
        print(
            f"Below {DATE_ACCURACY_THRESHOLD:.0%} date-accuracy threshold - relative dates are "
            "resolving wrong (check the current-date grounding in the extraction prompt)."
        )
        failed = True
    if llm_errors:
        print(f"{len(llm_errors)} case(s) could not be evaluated because the model provider failed.")
        failed = True
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
