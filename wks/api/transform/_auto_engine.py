"""Auto engine selection for transform operations."""

from pathlib import Path

from ._treesitter._language_map import _EXTENSION_TO_LANGUAGE
from .mime import normalize_extension

# Docling supported extensions (PDF, DOCX, PPTX, etc.)
_DOCLING_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}
_KIND_TO_ENGINE_TYPE = {
    "code": "treesitter",
    "document": "docling",
    "text": "textpass",
    "binary": "binarypass",
}


def classify_input_kind(input_path: Path) -> str:
    """Classify input as code, document, text, or binary."""
    extension = normalize_extension(input_path.suffix)

    if extension in _EXTENSION_TO_LANGUAGE:
        return "code"

    if extension in _DOCLING_EXTENSIONS:
        return "document"

    try:
        with input_path.open("rb") as f:
            chunk = f.read(8192)
            if b"\x00" not in chunk:
                try:
                    chunk.decode("utf-8")
                    return "text"
                except UnicodeDecodeError:
                    pass
    except Exception:
        pass

    return "binary"


def select_auto_engine(input_path: Path) -> str:
    """Select transform engine automatically based on file extension and content.

    Args:
        input_path: Path to input file

    Returns:
        Engine type string: "treesitter", "docling", "textpass", or "binarypass"

    Raises:
        ValueError: If file cannot be analyzed
    """
    return _KIND_TO_ENGINE_TYPE[classify_input_kind(input_path)]


__all__ = ["classify_input_kind", "select_auto_engine"]
