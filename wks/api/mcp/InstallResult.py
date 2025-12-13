"""Status for a single MCP client registration attempt."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallResult:
    """Status for a single MCP client registration attempt."""

    client: str
    path: Path
    status: str
    message: str = ""
