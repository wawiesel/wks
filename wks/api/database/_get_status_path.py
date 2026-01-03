"""Get path to database status file."""

from pathlib import Path


def _get_status_path() -> Path:
    """Get path to database status file."""
    import os

    if "WKS_HOME" in os.environ:  # noqa: SIM108
        wks_home = os.environ["WKS_HOME"]
    else:
        wks_home = str(Path.home() / ".wks")
    return Path(wks_home) / "database.json"
