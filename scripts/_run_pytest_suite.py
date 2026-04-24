#!/usr/bin/env python3
"""Shared runner for pytest suite wrapper scripts."""

import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def run_pytest_suite(label: str, test_path: str, args: list[str]) -> int:
    """Run one pytest suite with consistent logging and exit behavior."""
    bin_dir = Path(sys.executable).parent
    pytest_cmd = str(bin_dir / "pytest") if (bin_dir / "pytest").exists() else "pytest"

    console.print(f"[bold blue]Running {label} Tests ({test_path})...[/bold blue]")

    try:
        result = subprocess.run([pytest_cmd, test_path, *args], check=False)
    except Exception as exc:
        console.print(f"[bold red]Error running {label.lower()} tests: {exc}[/bold red]")
        return 1

    if result.returncode != 0:
        console.print(f"[bold red]{label} Tests FAILED[/bold red]")
        return result.returncode

    console.print(f"[bold green]{label} Tests PASSED[/bold green]")
    return 0
