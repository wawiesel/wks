"""Auto engine selection for diff operations."""

from pathlib import Path


def select_auto_diff_engine(file1: Path, file2: Path) -> str:
    """Select diff engine automatically based on file extensions.

    Args:
        file1: Path to first file
        file2: Path to second file

    Returns:
        Engine type string: "sexp", "myers", or "bsdiff3"

    Raises:
        ValueError: If files cannot be analyzed
    """
    # Check if both are *.sexp files
    if file1.suffix == ".sexp" and file2.suffix == ".sexp":
        return "sexp"

    # Check if both are text files
    def is_text_file(file_path: Path) -> bool:
        """Check if file is text."""
        try:
            with file_path.open("rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return False
                try:
                    chunk.decode("utf-8")
                    return True
                except UnicodeDecodeError:
                    return False
        except Exception:
            return False

    if is_text_file(file1) and is_text_file(file2):
        return "myers"

    # Default to binary diff
    return "bsdiff3"


__all__ = ["select_auto_diff_engine"]
