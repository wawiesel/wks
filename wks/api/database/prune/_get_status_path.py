"""Get path to database status file."""

from pathlib import Path


def _get_status_path() -> Path:
    """Get path to database status file."""
    import os

    wks_home = os.environ.get("WKS_HOME", str(Path.home() / ".wks"))
    return Path(wks_home) / "database.json"
