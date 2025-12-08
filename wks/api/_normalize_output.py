"""Helper to normalize output dicts to use errors and warnings lists."""

from typing import Any


def normalize_output(output: dict[str, Any]) -> dict[str, Any]:
    """Normalize output dict to use errors and warnings lists.
    
    Converts:
    - "error" (str) -> "errors" (list[str])
    - Ensures "errors" and "warnings" are always present as lists
    
    Args:
        output: Output dict that may have "error" (str) or missing errors/warnings
        
    Returns:
        Normalized output dict with errors and warnings as lists
    """
    normalized = dict(output)
    
    # Convert "error" (str) to "errors" (list)
    if "error" in normalized:
        error_str = normalized.pop("error")
        if error_str:
            normalized["errors"] = [error_str]
        else:
            normalized["errors"] = []
    elif "errors" not in normalized:
        normalized["errors"] = []
    
    # Ensure warnings is present
    if "warnings" not in normalized:
        normalized["warnings"] = []
    
    return normalized

