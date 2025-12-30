"""Test transform engine."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _TestEngine(_TransformEngine):
    """Test engine that copies content."""

    def transform(self, input_path: Path, output_path: Path, options: dict[str, Any]) -> Iterator[str]:  # noqa: ARG002
        """Copy input to output."""
        yield "Starting transform..."
        content = input_path.read_text()
        yield "Reading content..."
        output_path.write_text(f"Transformed: {content}")
        yield "Complete"

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        """Get extension."""
        return "md"
