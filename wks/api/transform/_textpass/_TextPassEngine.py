from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _TextPassEngine(_TransformEngine):
    def transform(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any],  # noqa: ARG002
    ) -> Generator[str, None, list[str]]:
        yield "Reading text file..."
        try:
            content = input_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"TextPassEngine requires UTF-8 text: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to read text file: {exc}") from exc

        yield "Writing text file..."
        try:
            output_path.write_text(content, encoding="utf-8")
        except Exception as exc:
            raise RuntimeError(f"Failed to write text file: {exc}") from exc

        yield "Text pass-through complete"
        return []

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        return "txt"
