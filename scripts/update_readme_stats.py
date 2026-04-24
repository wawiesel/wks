#!/usr/bin/env python3
"""Update README.md from generated statistics in qa/metrics/."""

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

try:
    from stats_lib import generate_badges_md, generate_metrics_report
except ImportError as exc:
    print(f"Error importing stats_lib: {exc}", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
BADGES_START = "<!-- BEGIN BADGES -->"
BADGES_END = "<!-- END BADGES -->"
METRICS_START = "<!-- BEGIN GENERATED METRICS -->"
METRICS_END = "<!-- END GENERATED METRICS -->"


def _required_metrics_files(metrics_dir: Path) -> list[Path]:
    """Return the required generated metrics files for README updates."""
    return [
        metrics_dir / "mutations.json",
        metrics_dir / "coverage.json",
        metrics_dir / "tokens.json",
        metrics_dir / "ci.json",
    ]


def _load_stats_json() -> dict:
    """Load generated metrics and normalize them for README output."""
    metrics_dir = REPO_ROOT / "qa" / "metrics"
    required_files = _required_metrics_files(metrics_dir)
    missing_files = [path for path in required_files if not path.exists()]

    if missing_files:
        missing_display = ", ".join(str(path.relative_to(REPO_ROOT)) for path in missing_files)
        print(f"Skipping README statistics update; missing generated metrics: {missing_display}")
        return {}

    mutations = json.loads((metrics_dir / "mutations.json").read_text())
    coverage = json.loads((metrics_dir / "coverage.json").read_text())
    loc_stats = json.loads((metrics_dir / "tokens.json").read_text())
    ci_stats = json.loads((metrics_dir / "ci.json").read_text())
    traceability_path = metrics_dir / "traceability.json"
    traceability = json.loads(traceability_path.read_text()) if traceability_path.exists() else {}

    freshness = "fresh" if ci_stats.get("docker_freshness_input", 0) == 0 else "stale"
    return {
        "mutation_score": mutations.get("score", 0),
        "traceability_pct": traceability.get("summary", {}).get("coverage_pct", 0.0),
        "coverage_pct": coverage.get("coverage_pct", 0.0),
        "test_count": ci_stats.get("test_count", 0),
        "test_files": ci_stats.get("test_files", 0),
        "docker_freshness": freshness,
        "sections": loc_stats.get("sections", {}),
    }


def _replace_marked_block(content: str, start_marker: str, end_marker: str, replacement: str) -> str:
    """Replace a marker-delimited block."""
    start = content.find(start_marker)
    end = content.find(end_marker)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"README is missing required markers: {start_marker} ... {end_marker}")

    block_start = start + len(start_marker)
    return f"{content[:block_start]}\n{replacement}\n{content[end:]}"


def _update_readme_from_stats(stats: dict) -> None:
    """Update README.md from stats dictionary."""
    if not README_PATH.exists():
        print(f"Error: {README_PATH} not found", file=sys.stderr)
        sys.exit(1)

    content = README_PATH.read_text()
    content = _replace_marked_block(content, BADGES_START, BADGES_END, generate_badges_md(stats))
    content = _replace_marked_block(content, METRICS_START, METRICS_END, generate_metrics_report(stats))
    README_PATH.write_text(content)
    print(f"✅ Updated {README_PATH} with current statistics")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Update README statistics from qa/metrics/*.json")
    parser.parse_args()

    stats = _load_stats_json()
    if not stats:
        return
    _update_readme_from_stats(stats)


if __name__ == "__main__":
    main()
