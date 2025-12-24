"""Internet check helper."""

import socket


def has_internet(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    """Check for internet connectivity."""
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
        return True
    except OSError:
        return False
