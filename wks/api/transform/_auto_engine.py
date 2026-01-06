"""Auto engine selection for transform operations."""

from pathlib import Path

from ._treesitter._language_map import _EXTENSION_TO_LANGUAGE
from .mime import normalize_extension

# Docling supported extensions (PDF, DOCX, PPTX, etc.)
_DOCLING_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}


def select_auto_engine(input_path: Path) -> str:
    """Select transform engine automatically based on file extension and content.

    Args:
        input_path: Path to input file

    Returns:
        Engine type string: "treesitter", "docling", "textpass", or "binarypass"

    Raises:
        ValueError: If file cannot be analyzed
    """
    extension = normalize_extension(input_path.suffix)

    # Check if it's a code extension (TreeSitter)
    if extension in _EXTENSION_TO_LANGUAGE:
        return "treesitter"

    # Check if it's a docling-supported extension
    if extension in _DOCLING_EXTENSIONS:
        return "docling"

    # Check if it's text
    try:
        # Try to read as text to verify it's text
        with input_path.open("rb") as f:
            chunk = f.read(8192)
            if b"\x00" not in chunk:
                # No null bytes, likely text
                try:
                    chunk.decode("utf-8")
                    return "textpass"
                except UnicodeDecodeError:
                    pass
    except Exception:
        pass

    # Default to binary pass-through
    return "binarypass"


__all__ = ["select_auto_engine"]
