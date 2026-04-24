#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def run_command(command, description):
    venv_dir = Path.cwd() / "venv"
    venv_bin = venv_dir / "bin"

    tool_name = command[0]
    venv_tool_path = venv_bin / tool_name

    run_env = None

    if venv_tool_path.exists():
        command[0] = str(venv_tool_path)

        run_env = os.environ.copy()
        run_env["PATH"] = f"{venv_bin}:{run_env.get('PATH', '')}"
        run_env["VIRTUAL_ENV"] = str(venv_dir)
        run_env.pop("PYTHONHOME", None)

        console.print(f"[bold blue]Running {description} (using venv)...[/bold blue]")
    else:
        console.print(f"[bold blue]Running {description}...[/bold blue]")
        pass

    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, env=run_env)
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
    args = sys.argv[1:]
    targets = args if args else ["wks"]

    if not run_command(["mypy", *targets], "Mypy Type Checking"):
        sys.exit(1)


if __name__ == "__main__":
    main()
