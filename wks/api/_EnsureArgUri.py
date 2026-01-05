"""Internal helper for API commands to reduce boilerplate."""

from pathlib import Path
from typing import Any

from .StageResult import StageResult
from .URI import URI


class _EnsureArgUri:
    """Helper to validate URI refers to an existing local file and resolve it to a Path."""

    @staticmethod
    def ensure(
        uri: URI,
        result_obj: StageResult,
        output_cls: Any,
        vault_path: Path | None = None,
        uri_field: str | None = "path",
        **default_fields: Any,
    ) -> Path | None:
        """Helper to validate URI refers to an existing local file and resolve it to a Path.

        Args:
            uri: The URI to validate/resolve.
            result_obj: The StageResult object to populate on failure.
            output_cls: The Pydantic model class for the output.
            vault_path: Optional root for resolving vault:/// URIs.
            uri_field: Field name for the URI/Path in output (e.g. 'path' or 'source_uri').
                       If None, it's not included in the output.
            **default_fields: Default values for required fields in output_cls.

        Returns:
            Path object if valid and exists, None otherwise (StageResult already populated).
        """

        def _populate_error(err_msg: str, current_uri_val: str):
            kwargs = {"errors": [err_msg], **default_fields}
            if uri_field:
                kwargs[uri_field] = current_uri_val

            result_obj.output = output_cls(**kwargs).model_dump(mode="python")
            result_obj.result = f"Error: {err_msg}"
            result_obj.success = False

        try:
            path = uri.to_path(vault_path)
        except ValueError as e:
            _populate_error(str(e), str(uri))
            return None

        if not path.exists():
            _populate_error("File does not exist", str(path))
            result_obj.result = f"File not found: {path}"
            return None

        return path
