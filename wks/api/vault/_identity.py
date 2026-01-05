"""Link identity calculation."""

import hashlib

from wks.api.URI import URI
from wks.utils.uri_to_string import uri_to_string


def _identity(note_path: URI | str, line_number: int, column_number: int, target_uri: URI | str) -> str:
    """Generate deterministic ID for a link.

    Args:
        note_path: Note path URI (URI object or string)
        line_number: Line number where link appears
        column_number: Column number where link appears
        target_uri: Target URI (URI object or string)

    Returns:
        SHA-256 hash of the link identity
    """
    note_path_str = uri_to_string(note_path)
    target_uri_str = uri_to_string(target_uri)
    payload = f"{note_path_str}|{line_number}|{column_number}|{target_uri_str}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()
