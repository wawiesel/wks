import json
import tempfile
from pathlib import Path
from typing import Any


def write_status_file(status: dict[str, Any], *, wks_home: Path, filename: str) -> None:
    path = wks_home / filename
    path.parent.mkdir(parents=True, exist_ok=True)

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
