from pathlib import Path


def normalize_path(path: str | Path | None) -> Path:
    if path is None:
        raise ValueError("normalize_path requires a path")
    return Path(path).expanduser().absolute()
