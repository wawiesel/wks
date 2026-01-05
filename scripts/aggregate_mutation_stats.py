#!/usr/bin/env python3
"""Aggregate mutation statistics (mutations.json)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _get_mutation_stats_from_mutmut() -> tuple[int, int]:
    """Fallback: Parse stats from 'mutmut results --all true' if files don't exist."""
    mutmut_bin = shutil.which("mutmut")
    if not mutmut_bin:
        candidate = Path(sys.executable).parent / "mutmut"
        if candidate.exists():
            mutmut_bin = str(candidate)

    if not mutmut_bin:
        return 0, 0

    try:
        p_results = subprocess.run(
            [mutmut_bin, "results", "--all", "true"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

        killed = 0
        survived = 0

        for line in (p_results.stdout or "").splitlines():
            line = line.strip()
            if line.endswith(": killed"):
                killed += 1
            elif line.endswith(": survived"):
                survived += 1

        return killed, survived
    except Exception:
        return 0, 0


def main():
    mutants_dir = REPO_ROOT / "mutants"
    mutation_by_domain = {}

    if mutants_dir.exists():
        for stats_file in mutants_dir.glob("mutation_*.json"):
            try:
                data = json.loads(stats_file.read_text())
                domain = data.get("domain")
                if domain:
                    mutation_by_domain[domain] = {
                        "killed": data.get("killed", 0),
                        "survived": data.get("survived", 0),
                    }
            except Exception:
                continue

    total_killed = 0
    total_survived = 0

    # Sort for stability
    for d in sorted(mutation_by_domain.keys()):
        total_killed += mutation_by_domain[d]["killed"]
        total_survived += mutation_by_domain[d]["survived"]

    # Fallback: if no per-domain files found, try to get stats from mutmut directly
    if total_killed == 0 and total_survived == 0:
        total_killed, total_survived = _get_mutation_stats_from_mutmut()

    grand_total = total_killed + total_survived
    score = (total_killed / grand_total * 100) if grand_total > 0 else 0.0

    stats = {
        "score": round(score, 1),
        "killed": total_killed,
        "survived": total_survived,
        "domains": mutation_by_domain,
    }

    metrics_dir = REPO_ROOT / "qa" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    (metrics_dir / "mutations.json").write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(f"✅ Generated {metrics_dir}/mutations.json")


if __name__ == "__main__":
    main()
