import json
from collections import Counter
from datetime import datetime
from pathlib import Path

DATASET_PATH = Path(__file__).parents[1] / "eval" / "golden_dataset" / "cases.jsonl"
EXPECTED_CATEGORIES = {"extraction", "routing", "permission", "prompt_injection", "hitl"}
EXPECTED_ROUTES = {"employee", "manager", "executive", "clarify", "deny"}
EXPECTED_POLICIES = {"ALLOW", "DENY", "MASK", "ASK_CLARIFY"}
REQUIRED_FIELDS = {
    "case_id",
    "category",
    "tags",
    "actor_role",
    "entitlements",
    "consents",
    "messages",
    "request",
    "expected_route",
    "expected_policy",
    "gold_tasks",
    "forbidden_source_ids",
    "required_hitl",
    "expected_action",
}


def _load_cases() -> list[dict]:
    lines = DATASET_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_golden_dataset_has_target_size_and_balanced_primary_slices():
    cases = _load_cases()
    assert 100 <= len(cases) <= 150
    assert Counter(case["category"] for case in cases) == {category: 24 for category in EXPECTED_CATEGORIES}


def test_golden_dataset_schema_ids_and_references_are_valid():
    cases = _load_cases()
    ids = [case["case_id"] for case in cases]
    assert len(ids) == len(set(ids))

    for case in cases:
        assert REQUIRED_FIELDS <= case.keys()
        assert case["category"] in EXPECTED_CATEGORIES
        assert case["expected_route"] in EXPECTED_ROUTES
        assert case["expected_policy"] in EXPECTED_POLICIES
        assert isinstance(case["required_hitl"], bool)
        assert case["messages"] and case["request"] and case["expected_action"]

        message_ids = {message["id"] for message in case["messages"]}
        for message in case["messages"]:
            assert message["conversation_id"]
            assert message["text"].strip()
            assert datetime.fromisoformat(message["sent_at"]).tzinfo is not None
        assert set(case["forbidden_source_ids"]) <= message_ids
        for task in case["gold_tasks"]:
            assert task["title"].strip()
            assert set(task["source_ids"]) <= message_ids
            if task["due_at"] is not None:
                assert datetime.fromisoformat(task["due_at"]).tzinfo is not None


def test_sensitive_side_effects_require_hitl_unless_already_resolved_or_denied():
    cases = _load_cases()
    previews = [case for case in cases if case["expected_action"].startswith("preview_")]
    assert previews
    assert all(case["required_hitl"] for case in previews)

    duplicate_cases = [case for case in cases if "idempotency" in case["tags"]]
    assert duplicate_cases
    assert all("once" in case["expected_action"] or "duplicate" in case["expected_action"] for case in duplicate_cases)
