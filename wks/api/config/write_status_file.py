"""Write status to a JSON file."""

import json
import tempfile
from pathlib import Path
from typing import Any


def write_status_file(status: dict[str, Any], *, wks_home: Path, filename: str) -> None:
    """Write status to {WKS_HOME}/{filename}."""
    path = wks_home / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write via NamedTemporaryFile in target directory to avoid cross-device issues
    content = json.dumps(status, indent=2)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f"{path.name}.",
        suffix=".tmp",
    ) as fh:
        tmp_path = Path(fh.name)
        fh.write(content)

    tmp_path.replace(path)
