"""Binary pass-through transform engine."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _BinaryPassEngine(_TransformEngine):
    """Binary pass-through engine that copies binary files as-is."""

    def transform(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any],  # noqa: ARG002
    ) -> Generator[str, None, list[str]]:
        """Copy binary file as-is to output.

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
        yield "Reading binary file..."
        try:
            data = input_path.read_bytes()
        except Exception as exc:
            raise RuntimeError(f"Failed to read binary file: {exc}") from exc

        yield "Writing binary file..."
        try:
            output_path.write_bytes(data)
        except Exception as exc:
            raise RuntimeError(f"Failed to write binary file: {exc}") from exc

        yield "Binary pass-through complete"
        return []

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        """Get output file extension for binary pass-through.

        Args:
            options: Options (unused)

        Returns:
            "bin" extension
        """
        return "bin"
