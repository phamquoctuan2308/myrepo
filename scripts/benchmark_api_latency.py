"""Measure HTTP endpoint latency and write reproducible JSON/Markdown evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "eval" / "results" / "latency-latest.json"
DEFAULT_MD = ROOT / "eval" / "results" / "latency-latest.md"


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile from an empty sample")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_latencies(samples_ms: list[float]) -> dict[str, float]:
    return {
        "min_ms": round(min(samples_ms), 3),
        "mean_ms": round(statistics.fmean(samples_ms), 3),
        "p50_ms": round(percentile(samples_ms, 0.50), 3),
        "p95_ms": round(percentile(samples_ms, 0.95), 3),
        "p99_ms": round(percentile(samples_ms, 0.99), 3),
        "max_ms": round(max(samples_ms), 3),
    }


async def _request_once(
    client: httpx.AsyncClient,
    method: str,
    endpoint: str,
    body: dict[str, Any] | None,
    expected_status: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = await client.request(method, endpoint, json=body)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "elapsed_ms": elapsed_ms,
            "status_code": response.status_code,
            "passed": response.status_code == expected_status,
            "error": None,
        }
    except httpx.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "elapsed_ms": elapsed_ms,
            "status_code": None,
            "passed": False,
            "error": type(exc).__name__,
        }


async def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if args.token_env:
        token = os.getenv(args.token_env)
        if not token:
            raise ValueError(f"Environment variable {args.token_env!r} is not set")
        headers["Authorization"] = f"Bearer {token}"

    body = json.loads(args.json_body) if args.json_body else None
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), headers=headers, limits=limits, timeout=timeout
    ) as client:
        for _ in range(args.warmup):
            await _request_once(client, args.method, args.endpoint, body, args.expected_status)

        semaphore = asyncio.Semaphore(args.concurrency)

        async def measured_request() -> dict[str, Any]:
            async with semaphore:
                return await _request_once(client, args.method, args.endpoint, body, args.expected_status)

        samples = await asyncio.gather(*(measured_request() for _ in range(args.requests)))

    elapsed = [sample["elapsed_ms"] for sample in samples]
    success_count = sum(1 for sample in samples if sample["passed"])
    metrics = summarize_latencies(elapsed)
    success_rate = success_count / len(samples)
    passed = success_rate == 1.0 and metrics["p95_ms"] <= args.p95_threshold_ms
    return {
        "run_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url.rstrip("/"),
        "endpoint": args.endpoint,
        "method": args.method,
        "request_count": args.requests,
        "warmup_count": args.warmup,
        "concurrency": args.concurrency,
        "expected_status": args.expected_status,
        "success_count": success_count,
        "success_rate": round(success_rate, 6),
        "p95_threshold_ms": args.p95_threshold_ms,
        "metrics": metrics,
        "passed": passed,
        "failures": [sample for sample in samples if not sample["passed"]],
    }


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    status = "PASS" if report["passed"] else "FAIL"
    return f"""# API Latency Evidence

- Run at: `{report["run_at"]}`
- Target: `{report["method"]} {report["base_url"]}{report["endpoint"]}`
- Requests: `{report["request_count"]}` after `{report["warmup_count"]}` warm-up requests
- Concurrency: `{report["concurrency"]}`
- Success rate: `{report["success_rate"] * 100:.1f}%`
- Gate: **{status}** (`p95 <= {report["p95_threshold_ms"]:.0f} ms` and 100% expected statuses)

| Metric | Result |
|---|---:|
| Min | {metrics["min_ms"]:.3f} ms |
| Mean | {metrics["mean_ms"]:.3f} ms |
| P50 | {metrics["p50_ms"]:.3f} ms |
| P95 | {metrics["p95_ms"]:.3f} ms |
| P99 | {metrics["p99_ms"]:.3f} ms |
| Max | {metrics["max_ms"]:.3f} ms |
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--endpoint", default="/health")
    parser.add_argument("--method", choices=("GET", "POST"), default="GET")
    parser.add_argument("--json-body", help="JSON object sent for POST benchmarks")
    parser.add_argument("--token-env", help="Environment variable containing a bearer token")
    parser.add_argument("--expected-status", type=int, default=200)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--p95-threshold-ms", type=float, default=5000.0)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.requests < 1 or args.warmup < 0 or args.concurrency < 1:
        raise SystemExit("requests/concurrency must be positive and warmup must be non-negative")
    report = asyncio.run(run_benchmark(args))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
