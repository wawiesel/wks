"""MIME type and extension helpers for transform engines."""

from __future__ import annotations

import mimetypes
from pathlib import Path

_MIME_TO_EXTENSION: dict[str, str] = {
    "text/x-python": ".py",
    "application/x-python-code": ".py",
    "text/javascript": ".js",
    "application/javascript": ".js",
    "application/x-javascript": ".js",
    "application/typescript": ".ts",
    "text/x-typescript": ".ts",
    "application/json": ".json",
    "text/x-json": ".json",
    "text/x-yaml": ".yaml",
    "application/x-yaml": ".yaml",
    "text/markdown": ".md",
    "text/html": ".html",
    "text/css": ".css",
    "text/x-shellscript": ".sh",
    "application/x-sh": ".sh",
    "text/x-c": ".c",
    "text/x-c++": ".cpp",
    "text/x-java-source": ".java",
    "text/x-ruby": ".rb",
    "text/x-go": ".go",
    "text/x-rust": ".rs",
    "application/x-php": ".php",
    "text/x-toml": ".toml",
}

_EXTENSION_TO_MIME: dict[str, str] = {
    ".py": "text/x-python",
    ".js": "application/javascript",
    ".jsx": "application/javascript",
    ".ts": "application/typescript",
    ".tsx": "application/typescript",
    ".json": "application/json",
    ".yaml": "text/x-yaml",
    ".yml": "text/x-yaml",
    ".toml": "text/x-toml",
    ".md": "text/markdown",
    ".html": "text/html",
    ".css": "text/css",
    ".sh": "text/x-shellscript",
    ".bash": "text/x-shellscript",
    ".c": "text/x-c",
    ".h": "text/x-c",
    ".cpp": "text/x-c++",
    ".hpp": "text/x-c++",
    ".cc": "text/x-c++",
    ".java": "text/x-java-source",
    ".rb": "text/x-ruby",
    ".go": "text/x-go",
    ".rs": "text/x-rust",
    ".php": "application/x-php",
}


def normalize_extension(extension: str) -> str:
    """Normalize extension to lowercase, leading-dot form."""
    ext = extension.strip().lower()
    if not ext:
        return ""
    return ext if ext.startswith(".") else f".{ext}"


def guess_mime_type(path: Path) -> str:
    """Guess MIME type for a path, with a stable fallback."""
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type:
        return mime_type
    extension = normalize_extension(path.suffix)
    if extension in _EXTENSION_TO_MIME:
        return _EXTENSION_TO_MIME[extension]
    return "application/octet-stream"


def extension_for_mime(mime_type: str) -> str | None:
    """Resolve a canonical extension for a MIME type."""
    normalized = mime_type.strip().lower()
    if normalized in _MIME_TO_EXTENSION:
        return _MIME_TO_EXTENSION[normalized]
    guessed = mimetypes.guess_extension(normalized)
    return guessed


def mime_for_extension(extension: str) -> str | None:
    """Resolve a MIME type for a file extension."""
    normalized = normalize_extension(extension)
    if normalized in _EXTENSION_TO_MIME:
        return _EXTENSION_TO_MIME[normalized]
    return mimetypes.types_map.get(normalized)


__all__ = [
    "extension_for_mime",
    "guess_mime_type",
    "mime_for_extension",
    "normalize_extension",
]
