#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def main():
    args = sys.argv[1:]

    # Resolve pytest path relative to the python interpreter being used
    bin_dir = Path(sys.executable).parent
    pytest_cmd = "pytest"
    if (bin_dir / "pytest").exists():
        pytest_cmd = str(bin_dir / "pytest")

    test_path = "tests/smoke"

    console.print(f"[bold blue]Running Smoke Tests ({test_path})...[/bold blue]")

    cmd = [pytest_cmd, test_path]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            console.print("[bold red]Smoke Tests FAILED[/bold red]")
            sys.exit(result.returncode)
        else:
            console.print("[bold green]Smoke Tests PASSED[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error running smoke tests: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
