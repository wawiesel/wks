#!/usr/bin/env python3
import subprocess
import sys
import argparse
from rich.console import Console

console = Console()

def run_command(command, description):
    console.print(f"[bold blue]Running {description}...[/bold blue]")
    try:
        result = subprocess.run(
            command, 
            check=False, 
            capture_output=True, 
            text=True
        )
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
    args = parser.parse_args()

    success = True
    if args.fix:
        if not run_command(["ruff", "format", "."], "Ruff Formatting (Fix)"): success = False
        if not run_command(["ruff", "check", "--fix", "."], "Ruff Linting (Fix)"): success = False
    else:
        if not run_command(["ruff", "format", "--check", "."], "Ruff Formatting (Check)"): success = False
        if not run_command(["ruff", "check", "."], "Ruff Linting (Check)"): success = False
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
