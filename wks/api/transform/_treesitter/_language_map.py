"""Language inference for tree-sitter transforms."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wks.api.transform.mime import guess_mime_type, normalize_extension

_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".bash": "bash",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".java": "java",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
}

_MIME_TO_LANGUAGE: dict[str, str] = {
    "text/x-python": "python",
    "application/x-python-code": "python",
    "text/javascript": "javascript",
    "application/javascript": "javascript",
    "application/x-javascript": "javascript",
    "application/typescript": "typescript",
    "text/x-typescript": "typescript",
    "application/json": "json",
    "text/x-json": "json",
    "text/x-yaml": "yaml",
    "application/x-yaml": "yaml",
    "text/markdown": "markdown",
    "text/html": "html",
    "text/css": "css",
    "text/x-shellscript": "bash",
    "application/x-sh": "bash",
    "text/x-c": "c",
    "text/x-c++": "cpp",
    "text/x-java-source": "java",
    "text/x-ruby": "ruby",
    "text/x-go": "go",
    "text/x-rust": "rust",
    "application/x-php": "php",
    "text/x-toml": "toml",
}


def resolve_language(input_path: Path, options: dict[str, Any]) -> str:
    """Resolve a tree-sitter language from options, MIME type, or extension."""
    explicit = options.get("language")
    if explicit is not None:
        if not isinstance(explicit, str) or not explicit.strip():
            raise ValueError("treesitter 'language' must be a non-empty string when provided.")
        return explicit.strip()

    mime_override = options.get("mime_type")
    if mime_override is not None and not isinstance(mime_override, str):
        raise ValueError("treesitter 'mime_type' must be a string when provided.")

    mime_type = mime_override or guess_mime_type(input_path)
    if mime_type:
        normalized = mime_type.lower()
        lang = _MIME_TO_LANGUAGE.get(normalized)
        if lang:
            return lang

    extension = normalize_extension(input_path.suffix)
    if extension in _EXTENSION_TO_LANGUAGE:
        return _EXTENSION_TO_LANGUAGE[extension]

    raise ValueError(
        "treesitter requires an explicit 'language' or a recognizable MIME/extension "
        f"(mime={mime_type!r}, extension={extension!r})"
    )


__all__ = ["resolve_language"]
