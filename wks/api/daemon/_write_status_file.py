"""Write daemon status to daemon.json (UNO: single function)."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_status_file(status: dict[str, Any], *, wks_home: Path) -> None:
    """Write daemon status to {WKS_HOME}/daemon.json."""
    path = wks_home / "daemon.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write via NamedTemporaryFile in target directory to avoid cross-device issues
    content = json.dumps(status, indent=2)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix="daemon.",
        suffix=".tmp",
    ) as fh:
        tmp_path = Path(fh.name)
        fh.write(content)

    os.replace(tmp_path, path)
