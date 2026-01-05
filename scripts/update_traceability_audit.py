#!/usr/bin/env python3
"""Generate the traceability audit HTML report using the Hodor rule tooling."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HODOR_SCRIPT = REPO_ROOT / ".cursor" / "rules" / "Hodor" / "scripts" / "build_traceability_audit.py"
DEFAULT_REQ_DIRS = ["qa/reqs/mon"]
DEFAULT_TEST_ITEM_DIRS: list[str] = []
DEFAULT_TEST_SCAN_DIRS = ["tests/unit", "tests/integration", "tests/smoke"]
DEFAULT_OUT = REPO_ROOT / "qa" / "traceability_audit.html"
DEFAULT_METRICS_OUT = REPO_ROOT / "qa" / "metrics" / "traceability.json"

DATA_JSON_RE = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.DOTALL)


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
        help="Directory to scan for test docstrings with Requirements blocks (relative to repo).",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output HTML file path.")
    parser.add_argument("--title", default="WKS Traceability Audit", help="Report title.")
    parser.add_argument(
        "--subtitle",
        default="Audit-ready traceability from requirements to tests.",
        help="Report subtitle.",
    )
    parser.add_argument(
        "--metrics-out",
        default=str(DEFAULT_METRICS_OUT),
        help="Output JSON metrics file path.",
    )
    return parser.parse_args()


def _write_traceability_metrics(
    html_path: Path,
    metrics_path: Path,
    req_dirs: list[str],
    test_item_dirs: list[str],
    test_scan_dirs: list[str],
) -> None:
    if not html_path.exists():
        print(f"Error: traceability report not found at {html_path}", file=sys.stderr)
        raise SystemExit(1)

    html = html_path.read_text(encoding="utf-8")
    match = DATA_JSON_RE.search(html)
    if not match:
        print("Error: traceability report JSON payload not found.", file=sys.stderr)
        raise SystemExit(1)

    data = json.loads(match.group(1))
    summary = data.get("summary", {})

    try:
        report_path = str(html_path.relative_to(REPO_ROOT))
    except ValueError:
        report_path = str(html_path)

    payload = {
        "sources": {
            "requirements": req_dirs,
            "test_items": test_item_dirs,
            "test_scan": test_scan_dirs,
            "report": report_path,
        },
        "summary": {
            "requirements": {
                "total": summary.get("requirements_total", 0),
                "linked": summary.get("requirements_linked", 0),
                "unlinked": summary.get("requirements_unlinked", 0),
            },
            "tests": {
                "total": summary.get("tests_total", 0),
                "linked": summary.get("tests_linked", 0),
                "unlinked": summary.get("tests_unlinked", 0),
            },
            "links_total": summary.get("links_total", 0),
            "coverage_pct": summary.get("coverage_pct", 0.0),
        },
    }

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"✅ Saved traceability metrics to {metrics_path}")


def main() -> int:
    args = parse_args()
    req_dirs = args.req_dir or DEFAULT_REQ_DIRS
    test_item_dirs = args.test_dir or DEFAULT_TEST_ITEM_DIRS
    test_scan_dirs = args.test_scan_dir or DEFAULT_TEST_SCAN_DIRS
    metrics_out = Path(args.metrics_out)

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
    _write_traceability_metrics(Path(args.out), metrics_out, req_dirs, test_item_dirs, test_scan_dirs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
