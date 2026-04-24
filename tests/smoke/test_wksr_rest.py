"""Smoke tests for the installed WKS REST entry point."""

import shutil
import subprocess
from pathlib import Path


def _find_wksr_command() -> str:
    """Find the installed wksr command."""
    project_root = Path(__file__).parents[2]
    venv_wksr = project_root / "venv" / "bin" / "wksr"
    if venv_wksr.exists():
        return str(venv_wksr)
    wksr_path = shutil.which("wksr")
    if wksr_path:
        return wksr_path
    raise RuntimeError("wksr command not found. Please install the package: pip install -e .")


def test_wksr_help():
    """The installed REST entry point should start and describe itself."""
    result = subprocess.run([_find_wksr_command(), "--help"], capture_output=True, text=True)

    assert result.returncode == 0
    assert "Run the WKS REST server" in result.stdout
