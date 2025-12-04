#!/usr/bin/env python3
import subprocess
import sys
import argparse
from pathlib import Path
from rich.console import Console

console = Console()
SCRIPTS_DIR = Path(__file__).parent

def run_script(script_name, args=None):
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        console.print(f"[bold red]Error running {script_name}: {e}[/bold red]")
        return False

def main():
    parser = argparse.ArgumentParser(description="Run all quality checks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    args = parser.parse_args()

    success = True
    
    console.print("\n[bold cyan]=== 1. Formatting & Linting ===[/bold cyan]")
    format_args = ["--fix"] if args.fix else []
    if not run_script("check_format.py", format_args):
        success = False

    console.print("\n[bold cyan]=== 2. Type Checking ===[/bold cyan]")
    if not run_script("check_types.py"):
        success = False

    console.print("\n[bold cyan]=== 3. Complexity Analysis ===[/bold cyan]")
    if not run_script("check_complexity.py"):
        success = False

    if not success:
        console.print("\n[bold red]Overall Quality Check FAILED[/bold red]")
        sys.exit(1)
    else:
        console.print("\n[bold green]All Quality Checks PASSED[/bold green]")

if __name__ == "__main__":
    main()