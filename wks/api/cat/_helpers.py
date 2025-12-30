"""Private helpers for cat command."""

import mimetypes
import re
from pathlib import Path

from ..config.WKSConfig import WKSConfig


def _is_checksum(target: str) -> bool:
    """Check if target is a 64-character hex checksum."""
    return bool(re.match(r"^[a-f0-9]{64}$", target))


def _get_mime_type(file_path: Path) -> str:
    """Get MIME type for file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


def _select_engine(file_path: Path, override: str | None, config: WKSConfig) -> str:
    """Select engine based on MIME type or override."""
    if override:
        return override

    mime_type = _get_mime_type(file_path)
    cat_config = config.cat

    # Check mime_engines mapping
    if hasattr(cat_config, "mime_engines") and cat_config.mime_engines:
        # Exact match
        if mime_type in cat_config.mime_engines:
            return cat_config.mime_engines[mime_type]

        # Wildcard match (e.g., "text/*")
        base_type = mime_type.split("/")[0] + "/*"
        if base_type in cat_config.mime_engines:
            return cat_config.mime_engines[base_type]

    # Fall back to default engine
    return cat_config.default_engine or "cat"
