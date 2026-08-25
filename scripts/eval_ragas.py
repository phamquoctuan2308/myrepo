"""Evaluate Orbit's context-grounded summaries with the current RAGAS collections API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
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


async def _generate_response(case: dict[str, Any], *, api_key: str, base_url: str, model: str) -> str:
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
    )
    summarize_tool.get_llm = lambda: evaluator_application_llm
    context = "\n".join(case["retrieved_contexts"])
    return await summarize_tool.generate_summary(context, style="brief")


async def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    _install_ragas_vertexai_compatibility_shim()
    try:
        from openai import AsyncOpenAI
        from ragas.embeddings.base import embedding_factory
        from ragas.llms import llm_factory
        from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
    except ImportError as exc:
        detail = exc.name or str(exc)
        raise RuntimeError(
            f'Evaluation dependency import failed ({detail}). Run: pip install -e ".[eval]"'
        ) from exc

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Set OPENROUTER_API_KEY for application generation and RAGAS evaluation")

    cases = load_cases(args.dataset)
    client = AsyncOpenAI(api_key=api_key, base_url=args.base_url)
    evaluator_llm = llm_factory(args.evaluator_model, client=client)
    evaluator_embeddings = embedding_factory("openai", model=args.embedding_model, client=client)
    scorers = {
        "faithfulness": Faithfulness(llm=evaluator_llm),
        "answer_relevancy": AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
        "context_precision": ContextPrecision(llm=evaluator_llm),
        "context_recall": ContextRecall(llm=evaluator_llm),
    }

    results: list[dict[str, Any]] = []
    for case in cases:
        response = case.get("response") if args.use_stored_responses else None
        if not response:
            response = await _generate_response(
                case,
                api_key=api_key,
                base_url=args.base_url,
                model=args.application_model,
            )
        contexts = case["retrieved_contexts"]
        scores = {
            "faithfulness": _numeric_score(
                await scorers["faithfulness"].ascore(
                    user_input=case["user_input"], response=response, retrieved_contexts=contexts
                )
            ),
            "answer_relevancy": _numeric_score(
                await scorers["answer_relevancy"].ascore(user_input=case["user_input"], response=response)
            ),
            "context_precision": _numeric_score(
                await scorers["context_precision"].ascore(
                    user_input=case["user_input"],
                    reference=case["reference"],
                    retrieved_contexts=contexts,
                )
            ),
            "context_recall": _numeric_score(
                await scorers["context_recall"].ascore(
                    user_input=case["user_input"],
                    reference=case["reference"],
                    retrieved_contexts=contexts,
                )
            ),
        }
        results.append(
            {
                "case_id": case["case_id"],
                "user_input": case["user_input"],
                "response": response,
                "scores": scores,
            }
        )

    averages = {metric: sum(result["scores"][metric] for result in results) / len(results) for metric in THRESHOLDS}
    checks = {
        metric: {
            "value": round(averages[metric], 6),
            "threshold": threshold,
            "passed": averages[metric] >= threshold,
        }
        for metric, threshold in THRESHOLDS.items()
    }
    return {
        "run_at": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset.relative_to(ROOT) if args.dataset.is_relative_to(ROOT) else args.dataset),
        "case_count": len(results),
        "application_model": args.application_model,
        "evaluator_provider": "openrouter",
        "evaluator_model": args.evaluator_model,
        "embedding_model": args.embedding_model,
        "stored_responses": args.use_stored_responses,
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
    return f"""# RAGAS Evaluation Evidence

- Run at: `{report["run_at"]}`
- Dataset: `{report["dataset"]}` ({report["case_count"]} cases)
- Application model: `{report["application_model"]}`
- Evaluator: `{report["evaluator_provider"]}/{report["evaluator_model"]}`
- Embeddings: `{report["embedding_model"]}`
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
