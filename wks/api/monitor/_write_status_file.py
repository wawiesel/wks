"""Write monitor status to monitor.json (UNO: single function)."""

import json
import tempfile
from pathlib import Path
from typing import Any


def write_status_file(status: dict[str, Any], *, wks_home: Path) -> None:
    """Write monitor status to {WKS_HOME}/monitor.json."""
    path = wks_home / "monitor.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write via NamedTemporaryFile in target directory to avoid cross-device issues
    content = json.dumps(status, indent=2)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix="monitor.",
        suffix=".tmp",
    ) as fh:
        tmp_path = Path(fh.name)
        fh.write(content)

    tmp_path.replace(path)
