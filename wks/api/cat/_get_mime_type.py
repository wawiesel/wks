import mimetypes
from pathlib import Path


def _get_mime_type(file_path: Path) -> str:
    """Get MIME type for file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"
