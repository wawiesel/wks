"""Validate backend type and set error result if invalid."""

from ..StageResult import StageResult
from .DaemonConfig import _BACKEND_REGISTRY


def _validate_backend_type(
    result_obj: StageResult,
    backend_type: str,
    output_class: type,
    status_field: str,
) -> bool:
    """Validate backend type and set error result if invalid.

    Args:
        result_obj: StageResult to update if validation fails
        backend_type: Backend type to validate
        output_class: Output schema class to instantiate
        status_field: Name of status field in output (e.g., "running", "stopped", "installed")

    Returns:
        True if valid, False if invalid (and result_obj is already set)
    """
    if backend_type not in _BACKEND_REGISTRY:
        error_msg = f"Unsupported daemon backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})"
        result_obj.result = f"Error: {error_msg}"
        result_obj.output = output_class(
            errors=[error_msg],
            warnings=[],
            message=error_msg,
            **{status_field: False},
        ).model_dump(mode="python")
        result_obj.success = False
        return False
    return True

