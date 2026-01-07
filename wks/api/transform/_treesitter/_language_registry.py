"""Tree-sitter language registry."""

from __future__ import annotations

import importlib

from tree_sitter import Language, Parser

# Mapping of canonical language names to (module, attribute) pairs.
_LANGUAGE_SOURCES: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language"),
    "json": ("tree_sitter_json", "language"),
    "yaml": ("tree_sitter_yaml", "language"),
    "toml": ("tree_sitter_toml", "language"),
    "markdown": ("tree_sitter_markdown", "language"),
    "html": ("tree_sitter_html", "language"),
    "css": ("tree_sitter_css", "language"),
    "bash": ("tree_sitter_bash", "language"),
    "c": ("tree_sitter_c", "language"),
    "cpp": ("tree_sitter_cpp", "language"),
    "java": ("tree_sitter_java", "language"),
    "ruby": ("tree_sitter_ruby", "language"),
    "go": ("tree_sitter_go", "language"),
    "rust": ("tree_sitter_rust", "language"),
    "php": ("tree_sitter_php", "language"),
}

_CACHE: dict[str, Language] = {}


class UnsupportedTreeSitterLanguageError(ValueError):
    """Raised when a requested tree-sitter language is unavailable."""


def _load_language(language: str) -> Language:
    if language in _CACHE:
        return _CACHE[language]

    source = _LANGUAGE_SOURCES.get(language)
    if source is None:
        raise UnsupportedTreeSitterLanguageError(language)

    module_name, attr_name = source
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ImportError(
            f"Tree-sitter module '{module_name}' is required for language '{language}'. "
            f"Install it with: pip install {module_name}"
        ) from exc

    language_obj = getattr(module, attr_name, None)
    if callable(language_obj):
        language_obj = language_obj()
    if language_obj is None:
        raise RuntimeError(f"Module {module_name} does not expose a tree-sitter Language entry.")

    if not isinstance(language_obj, Language):
        try:
            language_obj = Language(language_obj)
        except Exception as exc:
            raise RuntimeError(f"Failed to wrap language from {module_name}: {exc}") from exc

    _CACHE[language] = language_obj
    return language_obj


def get_parser_for_language(language: str) -> Parser:
    """Return a parser configured for the requested language."""

    language_obj = _load_language(language)
    parser = Parser()
    parser.language = language_obj
    return parser


def supported_languages() -> tuple[str, ...]:
    """Return all languages that can be loaded."""

    return tuple(_LANGUAGE_SOURCES.keys())
