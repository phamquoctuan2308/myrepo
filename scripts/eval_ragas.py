"""Evaluate Orbit's context-grounded summaries with the current RAGAS collections API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
if os.getenv("RAGAS_ENABLE_LANGSMITH", "").lower() not in {"1", "true", "yes"}:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"

DEFAULT_DATASET = ROOT / "eval" / "ragas" / "conversation_summary_cases.jsonl"
DEFAULT_JSON = ROOT / "eval" / "results" / "ragas-latest.json"
DEFAULT_MD = ROOT / "eval" / "results" / "ragas-latest.md"
THRESHOLDS = {
    "faithfulness": 0.70,
    "answer_relevancy": 0.70,
    "context_precision": 0.60,
    "context_recall": 0.60,
}

ANSWER_RELEVANCY_PROMPT_LANGUAGE = "vietnamese"
ANSWER_RELEVANCY_PROMPT_PROFILE = "vietnamese-summary-v1"


def _localize_answer_relevancy_prompt(scorer: Any) -> None:
    """Keep RAGAS' reverse-question judge in the same language as Orbit's answers.

    RAGAS 0.4.x ships English-only instructions and examples for AnswerRelevancy. The metric
    generates questions from each answer and compares their embeddings with the original user
    input, so allowing those generated questions to switch to English confounds answer quality
    with cross-language embedding similarity. We keep the metric and threshold unchanged while
    fixing its evaluator prompt to deterministic Vietnamese instructions/examples.
    """
    prompt = getattr(scorer, "question_generation", None) or getattr(scorer, "prompt", None)
    if prompt is None:
        raise TypeError("RAGAS AnswerRelevancy scorer does not expose a configurable prompt")
    input_model = prompt.input_model
    output_model = prompt.output_model
    prompt.instruction = (
        "Hãy suy ra MỘT câu hỏi bằng tiếng Việt mà toàn bộ câu trả lời đã cho trả lời trực tiếp, "
        "đồng thời xác định câu trả lời có né tránh hay không. Nếu câu trả lời là bản tóm tắt "
        "nhiều ý và mở đầu bằng một chủ đề trước dấu hai chấm, hãy hỏi tóm tắt toàn bộ chủ đề "
        "đó; không hỏi riêng một chi tiết, con số hoặc người được nhắc đến. Giữ nguyên tên riêng "
        "và thuật ngữ chủ đề. Đặt noncommittal bằng 1 nếu câu trả lời né tránh, mơ hồ hoặc không "
        "cam kết (ví dụ: 'Tôi không biết'); đặt bằng 0 nếu câu trả lời đưa ra thông tin cụ thể."
    )
    prompt.examples = [
        (
            input_model(
                response=(
                    "Kế hoạch triển khai và các rủi ro chính: Nhóm sẽ deploy bản mới vào thứ "
                    "Năm. Rủi ro còn lại là migration chậm và thiếu người trực vận hành."
                )
            ),
            output_model(
                question="Tóm tắt kế hoạch triển khai và các rủi ro chính.", noncommittal=0
            ),
        ),
        (
            input_model(response="Tôi không biết tính năng mới của sản phẩm đó."),
            output_model(
                question="Tính năng mới của sản phẩm đó là gì?", noncommittal=1
            ),
        ),
    ]
    prompt.language = ANSWER_RELEVANCY_PROMPT_LANGUAGE


class _RecordingLLMProxy:
    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.outputs: list[dict[str, Any]] = []

    async def agenerate(self, *args: Any, **kwargs: Any) -> Any:
        result = await self.delegate.agenerate(*args, **kwargs)
        self.outputs.append(
            {
                "question": getattr(result, "question", None),
                "noncommittal": getattr(result, "noncommittal", None),
            }
        )
        return result


async def _score_answer_relevancy_with_audit(
    scorer: Any, *, user_input: str, response: str
) -> tuple[Any, list[dict[str, Any]]]:
    original_llm = scorer.llm
    recording_llm = _RecordingLLMProxy(original_llm)
    scorer.llm = recording_llm
    try:
        score = await scorer.ascore(user_input=user_input, response=response)
    finally:
        scorer.llm = original_llm
    return score, recording_llm.outputs


def _load_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError(f"RAGAS report must be a JSON object: {path}")
    return report


def _responses_from_report(report: dict[str, Any], path: Path) -> dict[str, str]:
    responses: dict[str, str] = {}
    for case in report.get("cases", []):
        case_id = case.get("case_id")
        response = case.get("response")
        if isinstance(case_id, str) and isinstance(response, str) and response.strip():
            responses[case_id] = response
    if not responses:
        raise ValueError(f"No reusable case responses found in {path}")
    return responses


def _select_cases(
    cases: list[dict[str, Any]], requested_case_ids: list[str]
) -> list[dict[str, Any]]:
    if not requested_case_ids:
        return cases
    requested = set(requested_case_ids)
    known = {case["case_id"] for case in cases}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError("Unknown RAGAS case IDs: " + ", ".join(unknown))
    return [case for case in cases if case["case_id"] in requested]


def _install_ragas_vertexai_compatibility_shim() -> None:
    """Allow RAGAS 0.4.3 to import when the retired VertexAI integration is absent.

    RAGAS imports ``ChatVertexAI`` unconditionally even though this runner only uses its
    OpenAI-compatible factories. Modern ``langchain-community`` no longer ships that optional
    module. A placeholder type is sufficient for RAGAS' completion-capability type list and keeps
    the workaround local to this evaluation process.
    """
    module_name = "langchain_community.chat_models.vertexai"
    try:
        __import__(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        compatibility_module = types.ModuleType(module_name)
        compatibility_module.ChatVertexAI = type("ChatVertexAI", (), {})
        sys.modules[module_name] = compatibility_module


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            case = json.loads(raw_line)
            required = {"case_id", "user_input", "retrieved_contexts", "reference"}
            missing = required - case.keys()
            if missing:
                raise ValueError(f"{path}:{line_number} is missing: {', '.join(sorted(missing))}")
            if case["case_id"] in seen_ids:
                raise ValueError(f"Duplicate case_id: {case['case_id']}")
            if not case["retrieved_contexts"] or not all(
                isinstance(context, str) and context.strip() for context in case["retrieved_contexts"]
            ):
                raise ValueError(f"{case['case_id']} must have non-empty retrieved_contexts")
            seen_ids.add(case["case_id"])
            cases.append(case)
    if not cases:
        raise ValueError(f"No evaluation cases found in {path}")
    return cases


def _numeric_score(result: Any) -> float:
    value = getattr(result, "value", result)
    if not isinstance(value, int | float):
        raise TypeError(f"RAGAS returned a non-numeric score: {value!r}")
    return float(value)


def _source_revision() -> tuple[str, bool]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    return revision, dirty


async def _generate_response(
    case: dict[str, Any], *, api_key: str, base_url: str, model: str, request_timeout: float
) -> str:
    from langchain_openai import ChatOpenAI

    from src.agents.tools import summarize_tool
    from src.services import usage_service

    async def no_op_usage_log(**_: Any) -> None:
        return None

    usage_service.log_usage = no_op_usage_log
    evaluator_application_llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        timeout=request_timeout,
        max_retries=0,
    )
    summarize_tool.get_llm = lambda: evaluator_application_llm
    context = "\n".join(case["retrieved_contexts"])
    return await summarize_tool.generate_summary(
        context, style="brief", focus=case["user_input"]
    )


async def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    _install_ragas_vertexai_compatibility_shim()
    try:
        from openai import AsyncOpenAI
        from ragas.embeddings.base import embedding_factory
        from ragas.llms import llm_factory
        from ragas.metrics.collections import (
            AnswerRelevancy,
            ContextPrecision,
            ContextRecall,
            Faithfulness,
        )
    except ImportError as exc:
        detail = exc.name or str(exc)
        raise RuntimeError(
            f'Evaluation dependency import failed ({detail}). Run: pip install -e ".[eval]"'
        ) from exc

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Set OPENROUTER_API_KEY for application generation and RAGAS evaluation")

    all_cases = load_cases(args.dataset)
    cases = _select_cases(all_cases, args.case_id)
    selected_metrics = args.metric or list(THRESHOLDS)
    baseline_report = (
        _load_report(args.responses_from_report) if args.responses_from_report else None
    )
    report_responses = (
        _responses_from_report(baseline_report, args.responses_from_report)
        if baseline_report is not None and args.responses_from_report is not None
        else {}
    )
    if report_responses:
        missing_responses = [case["case_id"] for case in cases if case["case_id"] not in report_responses]
        if missing_responses:
            raise ValueError(
                "Response report is missing cases: " + ", ".join(missing_responses)
            )
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=args.base_url,
        timeout=args.request_timeout_seconds,
        max_retries=0,
    )
    evaluator_llm = llm_factory(args.evaluator_model, client=client)
    evaluator_embeddings = embedding_factory(
        "openai", model=args.embedding_model, client=client
    )
    scorers = {
        "faithfulness": Faithfulness(llm=evaluator_llm),
        "answer_relevancy": AnswerRelevancy(
            llm=evaluator_llm, embeddings=evaluator_embeddings
        ),
        "context_precision": ContextPrecision(llm=evaluator_llm),
        "context_recall": ContextRecall(llm=evaluator_llm),
    }
    _localize_answer_relevancy_prompt(scorers["answer_relevancy"])

    partial_rerun = bool(args.case_id or args.metric)
    baseline_results = {
        case["case_id"]: case
        for case in (baseline_report or {}).get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("case_id"), str)
    }
    if partial_rerun:
        missing_baseline = [
            case["case_id"] for case in all_cases if case["case_id"] not in baseline_results
        ]
        if missing_baseline:
            raise ValueError(
                "Partial reruns require --responses-from-report with every dataset case; missing: "
                + ", ".join(missing_baseline)
            )

    updated_results: dict[str, dict[str, Any]] = {
        case_id: dict(result) for case_id, result in baseline_results.items()
    }
    for case_index, case in enumerate(cases, start=1):
        print(f"[{case_index:02d}/{len(cases):02d}] prepare {case['case_id']}", flush=True)
        response = report_responses.get(case["case_id"])
        if response is None and args.use_stored_responses:
            response = case.get("response")
        if not response:
            response = await asyncio.wait_for(
                _generate_response(
                    case,
                    api_key=api_key,
                    base_url=args.base_url,
                    model=args.application_model,
                    request_timeout=args.request_timeout_seconds,
                ),
                timeout=args.metric_timeout_seconds,
            )
        contexts = case["retrieved_contexts"]
        all_score_calls = {
            "faithfulness": lambda: scorers["faithfulness"].ascore(
                user_input=case["user_input"], response=response, retrieved_contexts=contexts
            ),
            "answer_relevancy": lambda: _score_answer_relevancy_with_audit(
                scorers["answer_relevancy"],
                user_input=case["user_input"],
                response=response,
            ),
            "context_precision": lambda: scorers["context_precision"].ascore(
                user_input=case["user_input"],
                reference=case["reference"],
                retrieved_contexts=contexts,
            ),
            "context_recall": lambda: scorers["context_recall"].ascore(
                user_input=case["user_input"],
                reference=case["reference"],
                retrieved_contexts=contexts,
            ),
        }
        score_calls = {metric: all_score_calls[metric] for metric in selected_metrics}
        previous_result = updated_results.get(case["case_id"], {})
        scores: dict[str, float] = dict(previous_result.get("scores", {}))
        answer_relevancy_audit: list[dict[str, Any]] = list(
            previous_result.get("answer_relevancy_audit", [])
        )
        for metric, make_score_call in score_calls.items():
            print(f"[{case_index:02d}/{len(cases):02d}] score {case['case_id']} {metric}", flush=True)
            try:
                score_result = await asyncio.wait_for(
                    make_score_call(), timeout=args.metric_timeout_seconds
                )
            except TimeoutError as exc:
                raise RuntimeError(
                    f"Timed out scoring {case['case_id']} / {metric} after "
                    f"{args.metric_timeout_seconds:.0f}s"
                ) from exc
            if metric == "answer_relevancy":
                score_result, answer_relevancy_audit = score_result
            scores[metric] = _numeric_score(score_result)
        updated_results[case["case_id"]] = {
                **previous_result,
                "case_id": case["case_id"],
                "user_input": case["user_input"],
                "response": response,
                "scores": scores,
                "answer_relevancy_audit": answer_relevancy_audit,
            }

    result_order = all_cases if partial_rerun else cases
    results = [updated_results[case["case_id"]] for case in result_order]

    averages = {metric: sum(result["scores"][metric] for result in results) / len(results) for metric in THRESHOLDS}
    checks = {
        metric: {
            "value": round(averages[metric], 6),
            "threshold": threshold,
            "passed": averages[metric] >= threshold,
        }
        for metric, threshold in THRESHOLDS.items()
    }
    revision, dirty = _source_revision()
    return {
        "run_at": datetime.now(UTC).isoformat(),
        "source_revision": revision,
        "source_dirty": dirty,
        "dataset": str(args.dataset.relative_to(ROOT) if args.dataset.is_relative_to(ROOT) else args.dataset),
        "case_count": len(results),
        "application_model": args.application_model,
        "evaluator_provider": "openrouter",
        "evaluator_model": args.evaluator_model,
        "embedding_model": args.embedding_model,
        "answer_relevancy_prompt_language": ANSWER_RELEVANCY_PROMPT_LANGUAGE,
        "answer_relevancy_prompt_profile": ANSWER_RELEVANCY_PROMPT_PROFILE,
        "stored_responses": bool(args.use_stored_responses or report_responses),
        "response_source": (
            str(args.responses_from_report) if args.responses_from_report else "dataset_or_model"
        ),
        "partial_rerun": {
            "enabled": partial_rerun,
            "case_ids": [case["case_id"] for case in cases] if partial_rerun else [],
            "metrics": selected_metrics if partial_rerun else [],
        },
        "metrics": {metric: round(value, 6) for metric, value in averages.items()},
        "release_gate": {"passed": all(check["passed"] for check in checks.values()), "checks": checks},
        "cases": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for metric, check in report["release_gate"]["checks"].items():
        rows.append(
            f"| `{metric}` | {check['value']:.3f} | >= {check['threshold']:.2f} | "
            f"{'PASS' if check['passed'] else 'FAIL'} |"
        )
    status = "PASS" if report["release_gate"]["passed"] else "FAIL"
    partial_rerun = report.get("partial_rerun", {})
    rerun_scope = ""
    if partial_rerun.get("enabled"):
        rerun_scope = (
            "- Rerun scope: partial; cases `"
            + "`, `".join(partial_rerun["case_ids"])
            + "`; metrics `"
            + "`, `".join(partial_rerun["metrics"])
            + "` (other scores retained from the baseline report)\n"
        )
    return f"""# RAGAS Evaluation Evidence

- Run at: `{report["run_at"]}`
- Source revision: `{report["source_revision"]}` ({"dirty working tree" if report["source_dirty"] else "clean"})
- Dataset: `{report["dataset"]}` ({report["case_count"]} cases)
- Application model: `{report["application_model"]}`
- Evaluator: `{report["evaluator_provider"]}/{report["evaluator_model"]}`
- Embeddings: `{report["embedding_model"]}`
- Answer relevancy prompt: `{report["answer_relevancy_prompt_profile"]}`
{rerun_scope.rstrip()}
- Release gate: **{status}**

| Metric | Score | Gate | Status |
|---|---:|---:|---|
{chr(10).join(rows)}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--base-url", default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=float(os.getenv("RAGAS_REQUEST_TIMEOUT_SECONDS", "60")),
    )
    parser.add_argument(
        "--metric-timeout-seconds",
        type=float,
        default=float(os.getenv("RAGAS_METRIC_TIMEOUT_SECONDS", "90")),
    )
    parser.add_argument(
        "--application-model",
        default=os.getenv("RAGAS_APPLICATION_MODEL", "openai/gpt-5.6-luna"),
    )
    parser.add_argument(
        "--evaluator-model",
        default=os.getenv("RAGAS_EVALUATOR_MODEL", "openai/gpt-5.6-luna"),
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("RAGAS_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
    )
    parser.add_argument("--use-stored-responses", action="store_true")
    parser.add_argument(
        "--responses-from-report",
        type=Path,
        help="Reuse case responses from an earlier RAGAS JSON report while rescoring them.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Rerun only this case ID; repeat for multiple cases (requires a baseline report).",
    )
    parser.add_argument(
        "--metric",
        action="append",
        choices=tuple(THRESHOLDS),
        default=[],
        help="Rerun only this metric; repeat for multiple metrics (requires a baseline report).",
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = asyncio.run(run_evaluation(args))
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        print(f"RAGAS evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0 if report["release_gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
