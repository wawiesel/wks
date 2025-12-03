#!/usr/bin/env python3
import argparse
import subprocess
import sys

from rich.console import Console

console = Console()


def run_command(command, description, check=True):
    console.print(f"[bold blue]Running {description}...[/bold blue]")
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[bold red]FAILED: {description}[/bold red]")
            console.print(result.stdout)
            console.print(result.stderr)
            if check:
                sys.exit(result.returncode)
            return False
        else:
            console.print(f"[bold green]PASSED: {description}[/bold green]")
            return True
    except Exception as e:
        console.print(f"[bold red]Error running {description}: {e}[/bold red]")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run quality checks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    args = parser.parse_args()

    # 1. Formatting (Ruff)
    if args.fix:
        run_command(["ruff", "format", "."], "Ruff Formatting (Fix)")
        run_command(["ruff", "check", "--fix", "."], "Ruff Linting (Fix)")
    else:
        run_command(["ruff", "format", "--check", "."], "Ruff Formatting (Check)")
        run_command(["ruff", "check", "."], "Ruff Linting (Check)")

    # 2. Type Checking (Mypy)
    # Excluding tests from strict mypy for now as they often need loose typing, or we can include them.
    # Let's target the main package 'wks' for now.
    run_command(["mypy", "wks"], "Mypy Type Checking")

    # 3. Complexity (Lizard)
    # CCN <= 10, NLOC <= 100
    # lizard -l python -C 10 -L 100 wks/
    console.print("[bold blue]Running Lizard Complexity Analysis...[/bold blue]")
    result = subprocess.run(
        ["lizard", "-l", "python", "-C", "10", "-L", "100", "wks"],
        check=False,
        capture_output=True,
        text=True,
    )

    # Lizard returns 0 even if violations found, so we check output or use -w (warnings only) but
    # commonly we want to fail. Lizard with -C returns exit code 1 if violations found?
    # Let's verify. Actually lizard returns 0 by default.
    # We need to parse output or use a wrapper.
    # Wait, lizard has exit codes if using --warnings_only? No.
    # Let's check the output for specific warning markers or use a flag if available.
    # Ah, using -w will print warnings. We can check if stderr/stdout has content?
    # Actually, simply checking the output for violations is safest.

    if "!!!!" in result.stdout or "warning" in result.stdout.lower():
        # Lizard usually marks violations clearly.
        # Let's rely on a direct scan or just print it.
        # Better: Use subprocess to verify return code if we can make it fail.
        # lizard wks -C 10 -L 100 -x (exclude) ...
        # The simplified approach: print output and if violations exist, exit 1.

        # Let's use the standard way:
        # lizard --CCN 10 --length 100 wks
        # If any function exceeds, it shows it.
        pass

    # Re-run with strict exit code logic if possible, or just parse
    # A simpler way for lizard:
    cmd = ["lizard", "-l", "python", "-C", "10", "-L", "100", "wks"]
    lizard_out = subprocess.run(cmd, capture_output=True, text=True)

    if lizard_out.returncode != 0:  # Start simple, assuming it fails on error
        console.print(lizard_out.stdout)
        sys.exit(lizard_out.returncode)

    # Lizard does NOT return non-zero on violations by default.
    # We must check the output.
    violations = [line for line in lizard_out.stdout.splitlines() if "!!!!" in line]
    if violations:
        console.print("[bold red]Complexity Violations Found:[/bold red]")
        for v in violations:
            console.print(v)
        sys.exit(1)
    else:
        console.print("[bold green]PASSED: Lizard Complexity Analysis[/bold green]")


if __name__ == "__main__":
    main()
