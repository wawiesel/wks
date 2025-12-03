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

    test_path = "tests/unit"
    
    console.print(f"[bold blue]Running Unit Tests ({test_path})...[/bold blue]")
    
    cmd = [pytest_cmd, test_path]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            console.print(f"[bold red]Unit Tests FAILED[/bold red]")
            sys.exit(result.returncode)
        else:
            console.print(f"[bold green]Unit Tests PASSED[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error running unit tests: {e}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
