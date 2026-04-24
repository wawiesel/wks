from collections.abc import Generator
from pathlib import Path
from typing import Any

from ._TransformEngine import _TransformEngine


class _NullEngine(_TransformEngine):
    def transform(
        self,
        input_path: Path,  # noqa: ARG002
        output_path: Path,  # noqa: ARG002
        options: dict[str, Any],
    ) -> Generator[str, None, list[str]]:
        message = str(options.get("message") or "No transform available for this file type")
        raise RuntimeError(message)
        yield  # pragma: no cover

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        return "null"
