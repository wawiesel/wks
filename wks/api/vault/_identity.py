"""Link identity calculation."""

import hashlib


def _identity(note_path: str, line_number: int, column_number: int, target_uri: str) -> str:
    """Generate deterministic ID for a link."""
    payload = f"{note_path}|{line_number}|{column_number}|{target_uri}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()
