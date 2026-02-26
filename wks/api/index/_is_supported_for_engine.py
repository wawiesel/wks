"""Check whether a file path matches an engine's supported types."""

from pathlib import Path

from ..transform.mime import guess_mime_type, normalize_extension


def _is_supported_for_engine(supported_types: list[str] | None, file_path: Path) -> bool:
    """Return True when file_path is allowed by supported_types."""
    if supported_types is None or len(supported_types) == 0:
        return True

    normalized_types = [value.strip().lower() for value in supported_types if value.strip()]
    if len(normalized_types) == 0 or "*" in normalized_types:
        return True

    extension = normalize_extension(file_path.suffix)
    mime_type = guess_mime_type(file_path).lower()

    for value in normalized_types:
        if value.startswith("."):
            if extension == normalize_extension(value):
                return True
            continue
        if "/" in value:
            if value.endswith("/*"):
                if mime_type.startswith(value[:-1]):
                    return True
                continue
            if mime_type == value:
                return True
            continue
        if extension == normalize_extension(value):
            return True

    return False
