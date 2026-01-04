#!/usr/bin/env python3
"""Generate CI statistics (ci.json)."""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cmd(cmd: list[str]) -> tuple[int, str]:
    """Run command and return (returncode, stdout+stderr)."""
    result = subprocess.run(cmd, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _get_test_count() -> int:
    """Get total number of tests by running pytest --collect-only."""
    _rc, output = _run_cmd([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/"])
    # Parse "N tests collected" or just "N" from the last line
    for line in reversed(output.splitlines()):
        # Match "456 tests collected" or similar
        match = re.search(r"(\d+)\s+tests?\s+collected", line, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Match just a number at start of line (older pytest format)
        match = re.search(r"^(\d+)\s+", line.strip())
        if match:
            return int(match.group(1))
    return len(list((REPO_ROOT / "tests").rglob("test_*.py"))) * 4  # Fallback estimate


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--docker-freshness", choices=["fresh", "stale"], default="fresh")
    args = parser.parse_args()

    test_count = _get_test_count()
    test_files = len(list((REPO_ROOT / "tests").rglob("test_*.py")))

    # input arg gives text "fresh", we map to 0/1
    freshness_val = 0 if args.docker_freshness == "fresh" else 1

    stats = {
        "test_count": test_count,
        "test_files": test_files,
        "docker_freshness_input": freshness_val,
        "python_versions": ["3.10", "3.11", "3.12"],
        "installs": 1,
    }

    metrics_dir = REPO_ROOT / "qa" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    (metrics_dir / "ci.json").write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(f"✅ Generated {metrics_dir}/ci.json")


if __name__ == "__main__":
    main()
