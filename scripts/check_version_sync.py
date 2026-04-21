#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

import tomllib
from rich.console import Console

console = Console()

PYPROJECT_PATH = Path("pyproject.toml")
PACKAGE_INIT_PATH = Path("wks/__init__.py")
VERSION_PATTERN = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


def read_pyproject_version() -> str:
    if not PYPROJECT_PATH.exists():
        raise ValueError(f"Missing version source: {PYPROJECT_PATH}")
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Missing [project].version in {PYPROJECT_PATH}")
    return version


def read_package_init_version() -> str:
    if not PACKAGE_INIT_PATH.exists():
        raise ValueError(f"Missing version source: {PACKAGE_INIT_PATH}")
    match = VERSION_PATTERN.search(PACKAGE_INIT_PATH.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f'Missing __version__ = "..." in {PACKAGE_INIT_PATH}')
    return match.group(1)


def main() -> None:
    console.print("[bold blue]Running version sync check...[/bold blue]")
    pyproject_version = read_pyproject_version()
    package_version = read_package_init_version()

    if pyproject_version != package_version:
        console.print("[bold red]FAILED: Version sync check[/bold red]")
        console.print(f"{PYPROJECT_PATH}: {pyproject_version}")
        console.print(f"{PACKAGE_INIT_PATH}: {package_version}")
        sys.exit(1)

    console.print("[bold green]PASSED: Version sync check[/bold green]")


if __name__ == "__main__":
    main()
