#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def run_command(command, description):
    # Try to find the tool in the local .venv first
    venv_dir = Path.cwd() / ".venv"
    venv_bin = venv_dir / "bin"

    tool_name = command[0]
    venv_tool_path = venv_bin / tool_name

    run_env = None

    if venv_tool_path.exists():
        # Use the venv version of the tool
        command[0] = str(venv_tool_path)

        # Setup environment to prefer venv
        run_env = os.environ.copy()
        run_env["PATH"] = f"{venv_bin}:{run_env.get('PATH', '')}"
        run_env["VIRTUAL_ENV"] = str(venv_dir)
        # Unset PYTHONHOME if set, as it can conflict with venv
        run_env.pop("PYTHONHOME", None)

        console.print(f"[bold blue]Running {description} (using .venv)...[/bold blue]")
    else:
        # Fallback to resolving via PATH logic checks if needed, or just run as is
        console.print(f"[bold blue]Running {description}...[/bold blue]")
        # Resolve tool path manually if not absolute, just to be consistent with original code?
        # The original code resolved it relative to sys.executable bin_dir which is weird if we are system python.
        # Let's trust subprocess to find it in PATH if we didn't find it in venv.
        pass

    try:
        # If run_env is None, it uses the current process environment
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
    # Parse args manually to avoid argparse overhead for simple pass-through
    args = sys.argv[1:]
    targets = args if args else ["wks"]

    if not run_command(["mypy", *targets], "Mypy Type Checking"):
        sys.exit(1)


if __name__ == "__main__":
    main()
