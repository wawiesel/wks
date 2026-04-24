from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _BinaryPassEngine(_TransformEngine):
    def transform(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any],  # noqa: ARG002
    ) -> Generator[str, None, list[str]]:
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
        return "bin"
