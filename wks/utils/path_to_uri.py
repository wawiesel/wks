from pathlib import Path


def path_to_uri(path: Path) -> str:
    """Convert Path to file:// URI with hostname.

    Uses socket.gethostname() to include machine name for portable URIs.
    Format: file://hostname/absolute/path
    """
    import socket

    hostname = socket.gethostname()
    abs_path = path.resolve()
    # Build URI: file://hostname + absolute_path
    return f"file://{hostname}{abs_path}"
