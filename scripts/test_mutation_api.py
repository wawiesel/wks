#!/usr/bin/env python3
import argparse
import configparser
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

console = Console()
REPO_ROOT = Path(__file__).resolve().parents[1]

_CFG_SECTION = "wks.mutation"


@dataclass(frozen=True)
class MutationGate:
    min_kill_rate: float | None

    def __post_init__(self) -> None:
        if self.min_kill_rate is None:
            return
        if not (0.0 <= self.min_kill_rate <= 1.0):
            raise ValueError(f"min_kill_rate must be between 0.0 and 1.0, got {self.min_kill_rate!r}")


def _load_mutation_gate(setup_cfg: Path) -> MutationGate:
    parser = configparser.ConfigParser()
    parser.read(setup_cfg)
    if _CFG_SECTION not in parser:
        return MutationGate(min_kill_rate=None)

    raw = parser[_CFG_SECTION].get("min_kill_rate", fallback="").strip()
    if raw == "":
        return MutationGate(min_kill_rate=None)
    try:
        value = float(raw)
    except ValueError as e:
        raise ValueError(f"{setup_cfg}: [{_CFG_SECTION}] min_kill_rate must be a float, got {raw!r}") from e
    return MutationGate(min_kill_rate=value)


def _resolve_executable(name: str) -> str:
    bin_dir = Path(sys.executable).parent
    candidate = bin_dir / name
    if candidate.exists():
        return str(candidate)
    return name


def _run_results(mutmut_cmd: str, *, include_all: bool) -> tuple[int, str]:
    cmd = [mutmut_cmd, "results", "--all", "true" if include_all else "false"]
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    # mutmut writes all output to stdout in normal cases, but keep stderr for diagnostics.
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def _count_statuses(results_output: str) -> dict[str, int]:
    """
    Parse `mutmut results` output which is line-oriented:
        <mutant_key>: <status>
    """
    counts: dict[str, int] = {}
    for raw_line in results_output.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        _, status = line.rsplit(":", 1)
        status = status.strip().lower()
        if not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mutation testing for the Python API layer (wks/api) using mutmut")
    parser.add_argument(
        "--max-children",
        type=int,
        default=(os.cpu_count() or 1),
        help="Max parallel workers for mutmut (default: cpu count)",
    )
    parser.add_argument(
        "--results-only",
        action="store_true",
        help="Only show results (do not run mutation trials)",
    )
    parser.add_argument(
        "--all-results",
        action="store_true",
        help="Show all results including killed mutants (can be very verbose)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the full mutmut results listing (very verbose for large suites)",
    )
    parser.add_argument(
        "--fail-on-survivors",
        action="store_true",
        help="Exit non-zero if any mutants survive (useful for CI gating once stable)",
    )
    parser.add_argument(
        "--fail-on-untested",
        action="store_true",
        help="Exit non-zero if any mutants have 'no tests' (coverage gaps)",
    )
    parser.add_argument(
        "--min-kill-rate",
        type=float,
        default=None,
        help="Fail if mutation score (killed/(killed+survived)) is below this threshold, e.g. 0.90",
    )
    args = parser.parse_args()

    setup_cfg = REPO_ROOT / "setup.cfg"
    if not setup_cfg.exists():
        console.print("[bold red]setup.cfg not found[/bold red]")
        console.print("Expected: setup.cfg with a [mutmut] section and paths_to_mutate.")
        raise SystemExit(2)

    mutmut_cmd = _resolve_executable("mutmut")
    gate = _load_mutation_gate(setup_cfg)
    if args.min_kill_rate is not None:
        gate = MutationGate(min_kill_rate=args.min_kill_rate)

    if not args.results_only:
        console.print("[bold blue]Running mutation tests for wks/api...[/bold blue]")
        run_cmd = [mutmut_cmd, "run", "--max-children", str(args.max_children)]
        run_result = subprocess.run(run_cmd, cwd=str(REPO_ROOT), check=False)
        if run_result.returncode != 0:
            console.print("[bold red]mutmut run FAILED[/bold red]")
            raise SystemExit(run_result.returncode)

    console.print("[bold blue]Collecting mutation results...[/bold blue]")
    # Always collect the full results so we can compute accurate totals; printing is controlled by flags.
    results_rc, results_output = _run_results(mutmut_cmd, include_all=True)

    if results_rc != 0:
        console.print("[bold red]mutmut results FAILED[/bold red]")
        raise SystemExit(results_rc)

    counts = _count_statuses(results_output)
    survived = counts.get("survived", 0)
    no_tests = counts.get("no tests", 0)
    killed = counts.get("killed", 0)
    skipped = counts.get("skipped", 0)

    bad_statuses = {
        "timeout",
        "segfault",
        "suspicious",
        "not checked",
        "check was interrupted by user",
    }
    bad_total = sum(counts.get(s, 0) for s in bad_statuses)

    if args.verbose:
        if args.all_results:
            sys.stdout.write(results_output)
        else:
            # Default mutmut behavior hides killed; keep output manageable unless explicitly requested.
            filtered = "\n".join(line for line in results_output.splitlines() if not line.strip().endswith(": killed"))
            if filtered.strip():
                sys.stdout.write(filtered + "\n")

    console.print(
        "[bold blue]Mutation summary[/bold blue] "
        f"(killed={killed}, survived={survived}, no_tests={no_tests}, skipped={skipped}, bad={bad_total})"
    )

    checked = killed + survived
    mutation_score = (killed / checked) if checked > 0 else None
    if mutation_score is not None:
        console.print(f"[bold blue]Mutation score[/bold blue] {mutation_score:.3f} (killed/(killed+survived))")

    if bad_total > 0:
        console.print("[bold red]Mutation testing encountered unstable/error statuses[/bold red]")
        raise SystemExit(1)
    if args.fail_on_survivors and survived > 0:
        console.print("[bold red]Mutation testing failed (surviving mutants)[/bold red]")
        raise SystemExit(1)
    if args.fail_on_untested and no_tests > 0:
        console.print("[bold red]Mutation testing failed (mutants without tests)[/bold red]")
        raise SystemExit(1)

    if gate.min_kill_rate is not None:
        if mutation_score is None:
            console.print("[bold red]Mutation score gating failed[/bold red] (no checked mutants found)")
            raise SystemExit(1)
        if mutation_score < gate.min_kill_rate:
            console.print(
                "[bold red]Mutation score below threshold[/bold red] "
                f"(score={mutation_score:.3f}, required>={gate.min_kill_rate:.3f})"
            )
            raise SystemExit(1)

    console.print("[bold green]Mutation testing completed[/bold green]")


if __name__ == "__main__":
    main()
