"""Test transform engine."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _TestEngine(_TransformEngine):
    """Test engine that copies content."""

    def transform(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any],  # noqa: ARG002
    ) -> Generator[str, None, list[str]]:
        """Copy input to output."""
        yield "Starting transform..."
        content = input_path.read_text()
        yield "Reading content..."
        output_path.write_text(f"Transformed: {content}")
        output_path.write_text(f"Transformed: {content}")
        yield "Complete"
        return []

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        """Get extension."""
        return "md"
