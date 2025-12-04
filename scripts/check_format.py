#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def run_command(command, description):
    console.print(f"[bold blue]Running {description}...[/bold blue]")

    # Resolve tool path
    tool = command[0]
    bin_dir = Path(sys.executable).parent
    tool_path = bin_dir / tool
    if tool_path.exists():
        command[0] = str(tool_path)

    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[bold red]FAILED: {description}[/bold red]")
            console.print(result.stdout)
            console.print(result.stderr)
            return False
        else:
            console.print(f"[bold green]PASSED: {description}[/bold green]")
            return True
    except Exception as e:
        console.print(f"[bold red]Error running {description}: {e}[/bold red]")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run formatting and linting checks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    parser.add_argument("files", nargs="*", help="Files to check (default: all)")
    args = parser.parse_args()

    targets = args.files if args.files else ["."]

    success = True
    if args.fix:
        if not run_command(["ruff", "format"] + targets, "Ruff Formatting (Fix)"):
            success = False
        if not run_command(["ruff", "check", "--fix"] + targets, "Ruff Linting (Fix)"):
            success = False
    else:
        if not run_command(["ruff", "format", "--check"] + targets, "Ruff Formatting (Check)"):
            success = False
        if not run_command(["ruff", "check"] + targets, "Ruff Linting (Check)"):
            success = False

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
