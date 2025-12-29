"""Path expansion utility for sync commands."""

from collections.abc import Iterator
from pathlib import Path

from wks.utils.normalize_path import normalize_path


def expand_paths(
    path: Path,
    recursive: bool = False,
    extensions: set[str] | None = None,
) -> Iterator[Path]:
    """Expand a path into individual files for processing.

    Args:
        path: Path to file or directory
        recursive: If True and path is directory, recurse into subdirectories
        extensions: Optional set of file extensions to include (e.g. {".md", ".txt"})
                   If None, all files are included

    Yields:
        Individual file paths to process

    Raises:
        FileNotFoundError: If path does not exist
    """
    path = normalize_path(path)

    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path.is_file():
        # Single file: yield if extension matches (or no filter)
        if extensions is None or path.suffix.lower() in extensions:
            yield path
    elif path.is_dir():
        if recursive:
            # Recursive: walk all subdirectories
            for child in path.rglob("*"):
                if child.is_file() and (extensions is None or child.suffix.lower() in extensions):
                    yield child
        else:
            # Non-recursive: only immediate children
            for child in path.iterdir():
                if child.is_file() and (extensions is None or child.suffix.lower() in extensions):
                    yield child
