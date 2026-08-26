"""Run the complete test suite with the local 60% source-coverage release gate.

This is intentionally independent from the deployment CI workflow. Generated machine-readable
artifacts live under ``eval/results`` and are ignored by Git.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "eval" / "results"
BASE_TEMP = ROOT / ".tmp" / "pytest-coverage"


def build_command(minimum: float) -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-v",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        f"--basetemp={BASE_TEMP}",
        "--cov=src",
        "--cov-branch",
        f"--cov-fail-under={minimum:g}",
        "--cov-report=term-missing",
        f"--cov-report=xml:{RESULTS_DIR / 'coverage.xml'}",
        f"--cov-report=json:{RESULTS_DIR / 'coverage-latest.json'}",
        f"--cov-report=html:{RESULTS_DIR / 'htmlcov'}",
        f"--junitxml={RESULTS_DIR / 'test-results.junit.xml'}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum", type=float, default=60.0, help="Minimum total coverage percent")
    args = parser.parse_args()

    if importlib.util.find_spec("pytest_cov") is None:
        print('pytest-cov is missing. Install it with: pip install -e ".[dev]"', file=sys.stderr)
        return 2

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    BASE_TEMP.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(build_command(args.minimum), cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
