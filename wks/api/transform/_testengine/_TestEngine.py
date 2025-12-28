"""Test transform engine."""

from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _TestEngine(_TransformEngine):
    """Test engine that copies content."""

    def transform(self, input_path: Path, output_path: Path, options: dict[str, Any]) -> None:  # noqa: ARG002
        """Copy input to output."""
        content = input_path.read_text()
        output_path.write_text(f"Transformed: {content}")

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        """Get extension."""
        return "md"
