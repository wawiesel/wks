import hashlib


def _identity(from_uri: str, line_number: int, column_number: int, to_uri: str, remote_uri: str | None = None) -> str:
    payload = f"{from_uri}|{line_number}|{column_number}|{to_uri}|{remote_uri}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()
