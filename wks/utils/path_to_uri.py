from pathlib import Path


def path_to_uri(path: Path) -> str:
    """Convert Path to file:// URI with hostname.

    Uses socket.gethostname() to include machine name for portable URIs.
    Format: file://hostname/absolute/path
    """
    import socket

    from wks.utils.normalize_path import normalize_path

    hostname = socket.gethostname()
    abs_path = normalize_path(path)
    # Build URI: file://hostname + absolute_path
    return f"file://{hostname}{abs_path}"
