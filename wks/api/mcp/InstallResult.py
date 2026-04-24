from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallResult:
    client: str
    path: Path
    status: str
    message: str = ""
