from collections.abc import Iterator
from pathlib import Path

from .normalize_path import normalize_path


def expand_paths(
    path: Path,
    recursive: bool = False,
    extensions: set[str] | None = None,
) -> Iterator[Path]:
    path = normalize_path(path)

    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path.is_file():
        if extensions is None or path.suffix.lower() in extensions:
            yield path
    elif path.is_dir():
        if recursive:
            for child in path.rglob("*"):
                if child.is_file() and (extensions is None or child.suffix.lower() in extensions):
                    yield child
        else:
            for child in path.iterdir():
                if child.is_file() and (extensions is None or child.suffix.lower() in extensions):
                    yield child
