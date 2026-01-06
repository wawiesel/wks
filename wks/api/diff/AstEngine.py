"""AST diff engine."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path

from .DiffEngine import DiffEngine


class AstEngine(DiffEngine):
    """AST diff engine."""

    def diff(self, file1: Path, file2: Path, options: dict) -> str:
        """Compute AST diff.

        Args:
            file1: First file path
            file2: Second file path
            options: Options (expects "language")

        Returns:
            Unified diff of AST dumps or an identical message

        Raises:
            ValueError: If language is missing/unsupported or content is not valid code
            RuntimeError: If AST diff operation fails unexpectedly
        """
        language = options.get("language")
        if not language:
            raise ValueError("AST diff requires a non-empty 'language' option.")
        if language.lower() != "python":
            raise ValueError(f"AST diff supports only Python today (requested: {language}).")

        try:
            text_a = file1.read_text(encoding="utf-8")
            text_b = file2.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"AST diff requires UTF-8 text: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to read files for AST diff: {exc}") from exc

        try:
            tree_a = ast.parse(text_a, filename=str(file1))
            tree_b = ast.parse(text_b, filename=str(file2))
        except SyntaxError as exc:
            raise ValueError(f"AST diff requires valid Python syntax: {exc}") from exc

        dump_a = ast.dump(tree_a, include_attributes=False, indent=2)
        dump_b = ast.dump(tree_b, include_attributes=False, indent=2)

        if dump_a == dump_b:
            return "AST diff: no structural changes."

        diff_lines = difflib.unified_diff(
            dump_a.splitlines(),
            dump_b.splitlines(),
            fromfile=file1.name,
            tofile=file2.name,
            lineterm="",
        )
        return "AST diff (unified):\n" + "\n".join(diff_lines)
