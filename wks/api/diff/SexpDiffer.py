from __future__ import annotations

import difflib
from pathlib import Path

from .DiffEngine import DiffEngine


class SexpDiffer(DiffEngine):
    def diff(self, file1: Path, file2: Path, options: dict) -> str:  # noqa: ARG002
        if file1.suffix != ".sexp":
            raise ValueError(f"SexpDiffer requires *.sexp files (found: {file1.suffix})")
        if file2.suffix != ".sexp":
            raise ValueError(f"SexpDiffer requires *.sexp files (found: {file2.suffix})")

        try:
            text_a = file1.read_text(encoding="utf-8")
            text_b = file2.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"SexpDiffer requires UTF-8 text: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to read files for S-expression diff: {exc}") from exc

        if text_a == text_b:
            return "S-expression diff: no structural changes."

        diff_lines = difflib.unified_diff(
            text_a.splitlines(keepends=True),
            text_b.splitlines(keepends=True),
            fromfile=file1.name,
            tofile=file2.name,
            lineterm="",
        )
        return "S-expression diff (unified):\n" + "".join(diff_lines)
