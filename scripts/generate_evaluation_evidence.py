"""Build one honest Evaluation Evidence report from available machine-readable artifacts."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
OUTPUT = ROOT / "eval" / "EVALUATION_EVIDENCE.md"


def load_json(name: str) -> dict[str, Any] | None:
    path = RESULTS / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def source_revision() -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    return commit, dirty


def junit_summary() -> dict[str, int] | None:
    path = RESULTS / "test-results.junit.xml"
    if not path.exists():
        return None
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    fields = ("tests", "failures", "errors", "skipped")
    return {field: sum(int(suite.attrib.get(field, 0)) for suite in suites) for field in fields}


def status(value: bool | None) -> str:
    if value is None:
        return "PENDING"
    return "PASS" if value else "FAIL"


def fmt_percent(value: float | None) -> str:
    return "Pending" if value is None else f"{value * 100:.1f}%"


def build_report() -> str:
    commit, dirty = source_revision()
    coverage = load_json("coverage-latest.json")
    tests = junit_summary()
    acceptance = load_json("agent_acceptance_latest.json")
    tasks = load_json("task-extraction-latest.json")
    ragas = load_json("ragas-latest.json")
    latency = load_json("latency-latest.json")
    feedback = load_json("user-feedback-latest.json")

    coverage_percent = coverage.get("totals", {}).get("percent_covered") if coverage else None
    coverage_passed = coverage_percent >= 60 if coverage_percent is not None else None
    tests_passed = None
    if tests:
        tests_passed = tests["failures"] == 0 and tests["errors"] == 0
    acceptance_passed = acceptance.get("release_gate", {}).get("passed") if acceptance else None
    ragas_passed = ragas.get("release_gate", {}).get("passed") if ragas else None
    latency_passed = latency.get("passed") if latency else None
    feedback_status = feedback.get("status") if feedback else None
    feedback_ready = None if feedback_status in {None, "PENDING"} else feedback_status == "READY"

    test_result = "Pending"
    if tests:
        passed_count = tests["tests"] - tests["failures"] - tests["errors"] - tests["skipped"]
        test_result = f"{passed_count}/{tests['tests']} passed, {tests['skipped']} skipped"

    task_f1 = tasks.get("title_f1") if tasks else None
    date_accuracy = tasks.get("date_accuracy") if tasks else None
    acceptance_case_rate = acceptance.get("metrics", {}).get("case_pass_rate") if acceptance else None
    p95 = latency.get("metrics", {}).get("p95_ms") if latency else None
    feedback_rating = feedback.get("rating_mean") if feedback else None

    generated_at = datetime.now(UTC).isoformat()
    return f"""# Evaluation Evidence — Orbit

Generated at `{generated_at}` from source revision `{commit}`
{"with uncommitted evaluation changes" if dirty else "with a clean working tree"}.

This report never converts missing evidence into a passing score. `PENDING` means the runner or
protocol exists but no current result artifact is available.

## 1. Release evidence summary

| Evidence | Result | Gate | Status |
|---|---:|---:|---|
| Automated tests | {test_result} | No failures/errors | {status(tests_passed)} |
| Source coverage | {f"{coverage_percent:.1f}%" if coverage_percent is not None else "Pending"} | >=60% | {status(coverage_passed)} |
| Formal Agent acceptance | {fmt_percent(acceptance_case_rate)} case pass | Dataset gates | {status(acceptance_passed)} |
| Task title F1 | {fmt_percent(task_f1)} | >=70% | {status(task_f1 >= 0.70 if task_f1 is not None else None)} |
| Deadline accuracy | {fmt_percent(date_accuracy)} | >=70% | {status(date_accuracy >= 0.70 if date_accuracy is not None else None)} |
| RAGAS grounding | {fmt_percent(ragas.get("metrics", {}).get("faithfulness") if ragas else None)} faithfulness | All RAGAS gates | {status(ragas_passed)} |
| API latency P95 | {f"{p95:.1f} ms" if p95 is not None else "Pending"} | Configured runner gate | {status(latency_passed)} |
| User feedback | {f"{feedback_rating:.2f}/5" if feedback_rating is not None else "Pending"} | >=5 participants | {status(feedback_ready)} |

## 2. Current measured AI quality

- Formal acceptance: `{acceptance.get("run_at", "unknown") if acceptance else "Pending"}` using
  `{acceptance.get("provider", "unknown") if acceptance else "unknown"}/{acceptance.get("model", "unknown") if acceptance else "unknown"}`.
- Task extraction: `{tasks.get("case_count", 0) if tasks else 0}` cases; title precision
  `{fmt_percent(tasks.get("title_precision") if tasks else None)}`, recall
  `{fmt_percent(tasks.get("title_recall") if tasks else None)}`, F1 `{fmt_percent(task_f1)}`.
- Missing or failed gates remain release risks even when deterministic unit tests pass.

## 3. Reproducible commands

```powershell
python scripts/run_coverage.py
python scripts/benchmark_api_latency.py --base-url http://127.0.0.1:8000 --endpoint /health
python scripts/eval_user_agent.py
python scripts/eval_extract_tasks.py
python scripts/eval_ragas.py
python scripts/summarize_user_feedback.py
python scripts/generate_evaluation_evidence.py
```

## 4. Traceability and evidence locations

- Requirement-to-test-to-code map: [`TRACEABILITY_MATRIX.md`](TRACEABILITY_MATRIX.md)
- Manual scenarios: [`../MANUAL_TEST_CASES.md`](../MANUAL_TEST_CASES.md)
- Screenshot/video evidence: [`../Deliverables/evidence/`](../Deliverables/evidence/)
- Formal acceptance: [`results/agent_acceptance_latest.md`](results/agent_acceptance_latest.md)
- Evaluation protocols and commands: [`README.md`](README.md)

## 5. Evidence still requiring human/external execution

- RAGAS and formal Agent evaluation require real model credentials and consume quota.
- User satisfaction requires real anonymized participants; no synthetic rating is accepted.
- Latency must be measured against the actual target environment and recorded with its URL/model.
- Coverage/JUnit artifacts must be regenerated after material source changes.
"""


def main() -> int:
    OUTPUT.write_text(build_report(), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
