"""Tree-sitter transform engine."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine
from ._language_map import resolve_language

try:
    from tree_sitter_languages import get_parser

    TREESITTER_AVAILABLE = True
except ImportError:
    TREESITTER_AVAILABLE = False
    get_parser = None


class _TreeSitterEngine(_TransformEngine):
    """Tree-sitter transform engine for AST extraction."""

    def transform(
        self, input_path: Path, output_path: Path, options: dict[str, Any]
    ) -> Generator[str, None, list[str]]:
        """Transform source file into a tree-sitter AST representation.

        Args:
            input_path: Source file path
            output_path: Destination file path
            options: Engine options (requires "language"; optional "format")

        Raises:
            RuntimeError: If tree-sitter is unavailable or parse fails
            ValueError: If options are invalid
        """
        if not TREESITTER_AVAILABLE or get_parser is None:
            raise RuntimeError("tree-sitter support is unavailable. Install tree_sitter_languages to enable.")

        format_name = options.get("format", "sexp")
        if not isinstance(format_name, str):
            raise ValueError("treesitter 'format' must be a string")
        if format_name != "sexp":
            raise ValueError(f"treesitter format must be 'sexp' (found: {format_name!r})")

        yield f"Parsing {input_path.name} with tree-sitter..."

        language = resolve_language(input_path, options)
        try:
            parser = get_parser(language)
        except Exception as exc:
            raise ValueError(f"Unsupported tree-sitter language: {language}") from exc

        try:
            source_bytes = input_path.read_bytes()
        except Exception as exc:
            raise RuntimeError(f"Failed to read input file: {exc}") from exc

        try:
            tree = parser.parse(source_bytes)
            root = tree.root_node
        except Exception as exc:
            raise RuntimeError(f"Tree-sitter parse failed: {exc}") from exc

        yield "Serializing AST..."

        ast_text = root.sexp() if hasattr(root, "sexp") and callable(root.sexp) else self._node_to_sexp(root)

        output_path.write_text(ast_text + "\n", encoding="utf-8")

        return []

    def get_extension(self, _options: dict[str, Any]) -> str:
        """Get output file extension."""
        return "ast"

    def _node_to_sexp(self, node: Any) -> str:
        """Serialize node to a simple S-expression."""
        children = [self._node_to_sexp(child) for child in node.children]
        if not children:
            return f"({node.type})"
        return f"({node.type} {' '.join(children)})"
