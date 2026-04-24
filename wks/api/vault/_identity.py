import hashlib

from wks.api.config.URI import URI
from wks.api.config.uri_to_string import uri_to_string


def _identity(note_path: URI | str, line_number: int, column_number: int, target_uri: URI | str) -> str:
    note_path_str = uri_to_string(note_path)
    target_uri_str = uri_to_string(target_uri)
    payload = f"{note_path_str}|{line_number}|{column_number}|{target_uri_str}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()
