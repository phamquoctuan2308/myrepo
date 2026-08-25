import csv
from pathlib import Path

import pytest

from scripts.benchmark_api_latency import percentile, summarize_latencies
from scripts.eval_ragas import load_cases
from scripts.run_coverage import build_command
from scripts.summarize_user_feedback import load_responses, summarize

ROOT = Path(__file__).resolve().parents[1]


def test_latency_percentiles_use_linear_interpolation():
    values = [10.0, 20.0, 30.0, 40.0]

    assert percentile(values, 0.5) == 25.0
    assert percentile(values, 0.95) == pytest.approx(38.5)
    assert summarize_latencies(values)["p99_ms"] == pytest.approx(39.7)


def test_latency_percentile_rejects_empty_input():
    with pytest.raises(ValueError, match="empty sample"):
        percentile([], 0.95)


def test_coverage_command_enforces_local_source_gate():
    command = build_command(60)

    assert "--cov=src" in command
    assert "--cov-branch" in command
    assert "--cov-fail-under=60" in command
    assert any(argument.endswith("coverage-latest.json") for argument in command)
    assert any(argument.endswith("test-results.junit.xml") for argument in command)


def test_ragas_dataset_is_non_empty_synthetic_and_unique():
    cases = load_cases(ROOT / "eval" / "ragas" / "conversation_summary_cases.jsonl")

    assert len(cases) >= 5
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert all(case["retrieved_contexts"] for case in cases)
    assert all("response" not in case for case in cases)


def test_empty_feedback_is_pending_not_a_fake_pass():
    assert summarize([], minimum_participants=5) == {
        "status": "PENDING",
        "participant_count": 0,
        "response_count": 0,
        "minimum_participants": 5,
    }


def test_feedback_csv_is_validated_and_aggregated(tmp_path):
    path = tmp_path / "feedback.csv"
    fieldnames = [
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
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "response_id": "r-1",
                "participant_id": "p-1",
                "tested_at": "2026-08-25",
                "role": "employee",
                "scenario": "summary",
                "task_completed": "true",
                "rating_1_5": "4",
                "helpfulness_1_5": "5",
                "trust_1_5": "4",
                "would_use_again": "true",
                "issue_category": "none",
                "comment": "Hữu ích",
                "consent_to_use_anonymized_quote": "false",
            }
        )

    report = summarize(load_responses(path), minimum_participants=1)

    assert report["status"] == "READY"
    assert report["task_completion_rate"] == 1.0
    assert report["rating_mean"] == 4.0
    assert report["consented_anonymized_quotes"] == []


def test_openrouter_example_has_no_committed_secret():
    values = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value

    assert values["OPENROUTER_API_KEY"] == ""
    assert values["RAGAS_APPLICATION_MODEL"] == "openai/gpt-5.6-luna"
    assert values["RAGAS_EVALUATOR_MODEL"] == "openai/gpt-5.6-luna"
    assert values["RAGAS_EMBEDDING_MODEL"] == "openai/text-embedding-3-small"
