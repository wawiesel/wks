from pathlib import Path

from ._treesitter._language_map import _EXTENSION_TO_LANGUAGE
from .mime import normalize_extension

_DOCLING_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}
_KIND_TO_ENGINE_TYPE = {
    "code": "treesitter",
    "document": "docling",
    "text": "textpass",
    "binary": "binarypass",
}


def is_utf8_text(input_path: Path) -> bool:
    try:
        with input_path.open("rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return False
            chunk.decode("utf-8")
            return True
    except Exception:
        return False


def classify_input_kind(input_path: Path) -> str:
    extension = normalize_extension(input_path.suffix)

    if extension in _EXTENSION_TO_LANGUAGE:
        return "code"

    if extension in _DOCLING_EXTENSIONS:
        return "document"

    if is_utf8_text(input_path):
        return "text"

    return "binary"


def select_auto_engine(input_path: Path) -> str:
    return _KIND_TO_ENGINE_TYPE[classify_input_kind(input_path)]


__all__ = ["classify_input_kind", "is_utf8_text", "select_auto_engine"]
