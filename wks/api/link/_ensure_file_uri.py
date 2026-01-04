"""Internal helper for Link API commands to reduce boilerplate."""

from pathlib import Path
from typing import Any

from ..StageResult import StageResult
from ..URI import URI


def _ensure_file_uri(uri: URI, result_obj: StageResult, output_cls: Any, **default_fields: Any) -> Path | None:
    """Helper to validate URI is a file and exists, or populate result_obj with failure.

    Args:
        uri: The URI to validate.
        result_obj: The StageResult object to populate on failure.
        output_cls: The Pydantic model class for the output.
        **default_fields: Default values for required fields in output_cls.

    Returns:
        Path object if valid, None otherwise (StageResult already populated).
    """
    try:
        path = uri.path
    except ValueError:
        result_obj.output = output_cls(
            path=str(uri), errors=[f"Only file URIs are supported. Got {uri}"], **default_fields
        ).model_dump(mode="python")
        result_obj.result = f"Error: Only file URIs are supported. Got {uri}"
        result_obj.success = False
        return None

    if not path.exists():
        result_obj.output = output_cls(path=str(path), errors=["Path does not exist"], **default_fields).model_dump(
            mode="python"
        )
        result_obj.result = f"Path not found: {path}"
        result_obj.success = False
        return None

    return path
