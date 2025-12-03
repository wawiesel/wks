#!/usr/bin/env python3
import subprocess
import sys
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
    # Excluding tests from strict mypy for now as they often need loose typing
    if not run_command(["mypy", "wks"], "Mypy Type Checking"):
        sys.exit(1)

if __name__ == "__main__":
    main()
