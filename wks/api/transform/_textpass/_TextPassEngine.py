"""Text pass-through transform engine."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _TextPassEngine(_TransformEngine):
    """Text pass-through engine that copies text files as-is."""

    def transform(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any],  # noqa: ARG002
    ) -> Generator[str, None, list[str]]:
        """Copy text file as-is to output.

        Args:
            input_path: Source file path
            output_path: Destination file path
            options: Options (unused)

        Yields:
            Progress messages

        Returns:
            Empty list (no referenced URIs)

        Raises:
            RuntimeError: If file cannot be read or written
        """
        yield "Reading text file..."
        try:
            # Read as text to ensure it's valid text
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
        """Get output file extension for text pass-through.

        Args:
            options: Options (unused)

        Returns:
            "txt" extension
        """
        return "txt"
