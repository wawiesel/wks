"""Version command - returns WKS version information."""

import subprocess
from collections.abc import Iterator
from pathlib import Path

from ..StageResult import StageResult
from .._output_schemas.config import ConfigVersionOutput
from ...utils.get_package_version import get_package_version


def cmd_version() -> StageResult:
    """Get WKS version information.

    Returns:
        StageResult with version information
    """
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        yield (0.3, "Getting package version...")
        version = get_package_version()

        yield (0.6, "Checking git commit...")
        git_sha = None
        try:
            # Try to get git SHA from the project root
            project_root = Path(__file__).resolve().parents[3]
            sha_output = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                cwd=str(project_root),
            )
            git_sha = sha_output.decode().strip()
        except Exception:
            pass

        yield (1.0, "Complete")

        full_version = version
        if git_sha:
            full_version = f"{version} ({git_sha})"

        result_obj.result = f"WKS version: {full_version}"
        result_obj.output = ConfigVersionOutput(
            errors=[],
            warnings=[],
            version=version,
            git_sha=git_sha or "",
            full_version=full_version,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Getting version information...",
        progress_callback=do_work,
    )
