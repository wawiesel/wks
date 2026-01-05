from pathlib import Path
from urllib.parse import unquote

from wks.api.URI import URI


def uri_to_path(uri: str | URI) -> Path:
    """Convert file:// URI to Path.

    Handles both standard 'file:///' URIs and machine-prefixed 'file://host/' URIs.

    Args:
        uri: URI string or URI object like 'file:///Users/ww5/file.txt' or 'file://host/Users/ww5/file.txt'

    Returns:
        Path object

    Raises:
        ValueError: If URI is not a file URI.
    """
    # Convert URI object to string if needed
    uri_str = str(uri) if isinstance(uri, URI) else uri

    if uri_str.startswith("file://"):
        # Strip 'file://'
        path_part = uri_str[7:]

        # Find the first slash after the hostname (if any)
        # file://hostname/path -> hostname/path -> find('/') at hostname's end
        # file:///path -> /path -> find('/') at 0
        first_slash = path_part.find("/")
        path_part = path_part[first_slash:] if first_slash != -1 else "/"

        from wks.utils.normalize_path import normalize_path

        # URL decode and return Path
        return normalize_path(unquote(path_part))

    # If it's a URI object that's not a file URI, use its path property
    if isinstance(uri, URI):
        return uri.path

    return Path(uri_str)
