"""Run the memory evaluation harness only against an explicitly named disposable database."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def _validate_test_database() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit(
            "TEST_DATABASE_URL is required. Refusing to use DATABASE_URL so the harness cannot "
            "erase a development or production schema."
        )
    parsed = urlparse(url)
    database_name = parsed.path.rstrip("/").rsplit("/", 1)[-1].lower()
    if not database_name.endswith(("_test", "_tests", "_harness")):
        raise SystemExit(
            "TEST_DATABASE_URL must point to a disposable database whose name ends in "
            "_test, _tests, or _harness."
        )
    if url == os.environ.get("DATABASE_URL", "").strip():
        raise SystemExit("TEST_DATABASE_URL must not equal DATABASE_URL.")
    return url


def main() -> int:
    _validate_test_database()
    root = Path(__file__).resolve().parents[1]
    report_path = root / "eval" / "results" / "memory-harness.junit.xml"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "memory_harness or agent_quality_harness",
        "-q",
        f"--junitxml={report_path}",
    ]
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
