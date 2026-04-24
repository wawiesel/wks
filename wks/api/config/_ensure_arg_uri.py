from pathlib import Path
from typing import Any

from .StageResult import StageResult
from .URI import URI


def _ensure_arg_uri(
    uri: URI,
    result_obj: StageResult,
    output_cls: Any,
    vault_path: Path | None = None,
    uri_field: str | None = "path",
    **default_fields: Any,
) -> Path | None:
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
