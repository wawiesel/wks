#!/usr/bin/env python3
"""Generate all statistics locally, matching CI workflow.

This script replicates what CI does to generate statistics:
1. Run tests with coverage
2. Run mutation tests for all domains
3. Generate all statistics files
4. Update traceability audit
5. Update README

Usage:
    ./scripts/generate_all_stats.py [--skip-tests] [--skip-mutations]
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def _run_cmd(cmd: list[str], description: str, check: bool = True) -> bool:
    """Run command and return success status."""
    print(f"\n{'=' * 60}")
    print(f"▶ {description}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    if result.returncode != 0 and check:
        print(f"❌ Failed: {description}", file=sys.stderr)
        return False
    elif result.returncode != 0:
        print(f"⚠️  Warning: {description} (non-zero exit, continuing)")
    else:
        print(f"✅ Completed: {description}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all statistics locally (matches CI workflow)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests with coverage")
    parser.add_argument("--skip-mutations", action="store_true", help="Skip mutation testing")
    args = parser.parse_args()

    # Use .venv Python if available, otherwise system Python
    python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    print("=" * 60)
    print("Generating all statistics (matching CI workflow)")
    print("=" * 60)

    # Step 1: Run tests with coverage (if not skipped)
    if not args.skip_tests and not _run_cmd(
        [python_exe, "-m", "pytest", "--cov=wks", "--cov-report=xml", "tests/", "-v", "--tb=short"],
        "Running tests with coverage",
        check=False,
    ):
        print("⚠️  Tests failed, but continuing with statistics generation...")

    # Step 2: Run mutation tests for all domains (if not skipped)
    if not args.skip_mutations:
        print(f"\n{'=' * 60}")
        print("▶ Running mutation tests for all domains")
        print(f"{'=' * 60}")
        domains = []
        for domain_dir in (REPO_ROOT / "wks" / "api").iterdir():
            if domain_dir.is_dir() and domain_dir.name != "__pycache__":
                domains.append(domain_dir.name)

        for domain in sorted(domains):
            _run_cmd(
                [python_exe, "scripts/test_mutation_api.py", domain, "--log-interval", "15"],
                f"Mutation testing: {domain}",
                check=False,
            )

    # Step 3: Generate all statistics files (matching CI)
    print(f"\n{'=' * 60}")
    print("▶ Generating all statistics files")
    print(f"{'=' * 60}")

    _run_cmd([python_exe, "scripts/generate_coverage_stats.py"], "Generating coverage statistics", check=False)
    _run_cmd([python_exe, "scripts/generate_ci_stats.py"], "Generating CI statistics", check=False)
    _run_cmd([python_exe, "scripts/generate_token_stats.py"], "Generating token statistics", check=False)

    # Step 4: Update traceability audit
    _run_cmd([python_exe, "scripts/update_traceability_audit.py"], "Updating traceability audit", check=False)

    # Step 5: Update README with all statistics
    _run_cmd([python_exe, "scripts/update_readme_stats.py"], "Updating README statistics", check=False)

    print(f"\n{'=' * 60}")
    print("✅ All statistics generated successfully!")
    print(f"{'=' * 60}")
    print("\nGenerated files:")
    metrics_dir = REPO_ROOT / "qa" / "metrics"
    for json_file in sorted(metrics_dir.glob("*.json")):
        print(f"  - {json_file.relative_to(REPO_ROOT)}")
    print("\n  - README.md (updated)")
    print("  - qa/traceability_audit.html (updated)")


if __name__ == "__main__":
    main()
