#!/usr/bin/env python3
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
    # Parse args manually to avoid argparse overhead for simple pass-through
    args = sys.argv[1:]
    targets = args if args else ["wks"]

    if not run_command(["mypy"] + targets, "Mypy Type Checking"):
        sys.exit(1)


if __name__ == "__main__":
    main()
