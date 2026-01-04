#!/usr/bin/env python3
"""Update README.md from pre-generated statistics in qa/metrics/."""

import argparse
import json
import re
import sys
from pathlib import Path

# Fix path to allow importing from same directory
sys.path.append(str(Path(__file__).resolve().parent))

try:
    from stats_lib import (
        generate_badges_md,
        generate_domain_table,
        generate_full_report,
    )
except ImportError as e:
    print(f"Error importing stats_lib: {e}", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"


def _load_stats_json() -> dict:
    """Load stats from split JSON files and aggregate."""
    metrics_dir = REPO_ROOT / "qa" / "metrics"

    try:
        mutations = json.loads((metrics_dir / "mutations.json").read_text())
        coverage = json.loads((metrics_dir / "coverage.json").read_text())
        loc_stats = json.loads((metrics_dir / "tokens.json").read_text())
        ci_stats = json.loads((metrics_dir / "ci.json").read_text())
    except FileNotFoundError as e:
        print(f"Error: metrics files not found in {metrics_dir}: {e}", file=sys.stderr)
        sys.exit(1)

    # Reconstruct domain_stats
    domain_stats = {}
    all_domains = set(coverage.get("domains", {}).keys()) | set(mutations.get("domains", {}).keys())

    for d in all_domains:
        domain_stats[d] = {
            "coverage": coverage.get("domains", {}).get(d, 0.0),
            "mutation_killed": mutations.get("domains", {}).get(d, {}).get("killed", 0),
            "mutation_survived": mutations.get("domains", {}).get(d, {}).get("survived", 0),
        }

    # Interpret status from metrics
    cov_pct = coverage.get("pct", 0)
    cov_status = "✅ Pass" if cov_pct >= 100.0 else "⚠️ Below Target"

    mut_score = mutations.get("score", 0)

    freshness = "fresh" if ci_stats.get("docker_freshness_input", 0) == 0 else "stale"

    return {
        "mutation_score": mut_score,
        "mutation_killed": mutations.get("killed", 0),
        "mutation_survived": mutations.get("survived", 0),
        "domain_stats": domain_stats,
        "coverage_pct": cov_pct,
        "coverage_status": cov_status,
        "test_count": ci_stats.get("test_count", 0),
        "test_files": ci_stats.get("test_files", 0),
        "docker_freshness": freshness,
        "sections": loc_stats.get("sections", {}),
    }


def _update_readme_from_stats(stats: dict) -> None:
    """Update README.md from stats dictionary."""
    if not README_PATH.exists():
        print(f"Error: {README_PATH} not found", file=sys.stderr)
        sys.exit(1)

    # Generate full report content using stats_lib
    report = generate_full_report(stats)
    badges = generate_badges_md(stats)
    domain_table = generate_domain_table(stats.get("domain_stats", {}))

    if domain_table:
        domain_table = "\n\n### Per-Domain Quality\n\n" + domain_table

    # Update README
    content = README_PATH.read_text()

    # Replace badges section
    content = re.sub(r"(# WKS.*?\n\n)(.*?)(\n## Status)", rf"\1{badges}\n\3", content, flags=re.DOTALL)

    # Replace table section
    table_header = "## Code Quality Metrics\n\n"

    table_start = content.find(table_header)
    if table_start != -1:
        next_section = content.find("\n## ", table_start + len(table_header))
        if next_section == -1:
            next_section = content.find("\nAI-assisted", table_start)
        if next_section != -1:
            content = (
                content[: table_start + len(table_header)] + report + domain_table + "\n\n" + content[next_section:]
            )
        else:
            content = content[: table_start + len(table_header)] + report + domain_table
    else:
        content = re.sub(
            r"(## Code Quality Metrics\n\n)(.*?)(\n\n## |\nAI-assisted)",
            rf"\1{report}{domain_table}\n\n\3",
            content,
            flags=re.DOTALL,
        )

    README_PATH.write_text(content)
    print(f"✅ Updated {README_PATH} with current statistics")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Update README statistics from qa/metrics/*.json")
    parser.parse_args()

    stats = _load_stats_json()
    _update_readme_from_stats(stats)


if __name__ == "__main__":
    main()
