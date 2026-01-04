#!/usr/bin/env python3
"""Generate the traceability audit HTML report using the Hodor rule tooling."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HODOR_SCRIPT = REPO_ROOT / ".cursor" / "rules" / "Hodor" / "scripts" / "build_traceability_audit.py"
DEFAULT_REQ_DIRS = ["docs/specifications/requirements/mon"]
DEFAULT_TEST_ITEM_DIRS: list[str] = []
DEFAULT_TEST_SCAN_DIRS = ["tests/unit", "tests/integration", "tests/smoke"]
DEFAULT_OUT = REPO_ROOT / "docs" / "traceability" / "traceability_audit.html"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the traceability audit report (Hodor).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--req-dir", action="append", default=[], help="Requirement item directory (relative to repo).")
    parser.add_argument("--test-dir", action="append", default=[], help="Test item directory (relative to repo).")
    parser.add_argument(
        "--test-scan-dir",
        action="append",
        default=[],
        help="Directory to scan for in-test HODOR metadata comments (relative to repo).",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output HTML file path.")
    parser.add_argument("--title", default="WKS Traceability Audit", help="Report title.")
    parser.add_argument(
        "--subtitle",
        default="Audit-ready traceability from requirements to tests.",
        help="Report subtitle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    req_dirs = args.req_dir or DEFAULT_REQ_DIRS
    test_item_dirs = args.test_dir or DEFAULT_TEST_ITEM_DIRS
    test_scan_dirs = args.test_scan_dir or DEFAULT_TEST_SCAN_DIRS

    if not HODOR_SCRIPT.exists():
        print(
            "Error: Hodor script not found. Install the Hodor rule pack at .cursor/rules/Hodor.",
            file=sys.stderr,
        )
        return 1

    cmd = [
        sys.executable,
        str(HODOR_SCRIPT),
        "--root",
        str(REPO_ROOT),
        "--display-root",
        ".",
        "--out",
        str(args.out),
        "--title",
        args.title,
        "--subtitle",
        args.subtitle,
    ]
    for path in req_dirs:
        cmd.extend(["--req-dir", path])
    for path in test_item_dirs:
        cmd.extend(["--test-dir", path])
    for path in test_scan_dirs:
        cmd.extend(["--test-scan-dir", path])

    subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
