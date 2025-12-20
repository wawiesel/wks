from pathlib import Path
from urllib.parse import unquote


def uri_to_path(uri: str) -> Path:
    """Convert file:// URI to Path.

    Handles both standard 'file:///' URIs and machine-prefixed 'file://host/' URIs.

    Args:
        uri: URI string like 'file:///Users/ww5/file.txt' or 'file://host/Users/ww5/file.txt'

    Returns:
        Path object
    """
    if uri.startswith("file://"):
        # Strip 'file://'
        path_part = uri[7:]

        # Find the first slash after the hostname (if any)
        # file://hostname/path -> hostname/path -> find('/') at hostname's end
        # file:///path -> /path -> find('/') at 0
        first_slash = path_part.find("/")
        path_part = path_part[first_slash:] if first_slash != -1 else "/"

        # URL decode and return Path
        return Path(unquote(path_part))
    return Path(uri)
