import hashlib

from wks.api.config.URI import URI
from wks.api.config.uri_to_string import uri_to_string


def _identity(
    from_uri: URI | str, line_number: int, column_number: int, to_uri: URI | str, remote_uri: URI | str | None = None
) -> str:
    from_uri_str = uri_to_string(from_uri)
    to_uri_str = uri_to_string(to_uri)
    remote_uri_str = uri_to_string(remote_uri) if remote_uri else None
    payload = f"{from_uri_str}|{line_number}|{column_number}|{to_uri_str}|{remote_uri_str}".encode(
        "utf-8", errors="ignore"
    )
    return hashlib.sha256(payload).hexdigest()
