"""Path and URI conversion utilities for WKS.

The monitor database stores paths as URIs (file:///...) while configuration
uses regular paths (~/_vault, /Users/ww5/_vault). These utilities handle
conversion between the two forms.
"""

from pathlib import Path
from urllib.parse import unquote


def path_to_uri(path: Path) -> str:
    """Convert Path to file:// URI.

    Args:
        path: Path object

    Returns:
        URI string like 'file:///Users/ww5/file.txt'
    """
    return path.resolve().as_uri()


def uri_to_path(uri: str) -> Path:
    """Convert file:// URI to Path.

    Args:
        uri: URI string like 'file:///Users/ww5/file.txt'

    Returns:
        Path object
    """
    if uri.startswith('file://'):
        # Remove file:// prefix
        path_str = uri[7:]
        # URL decode any percent-encoded characters
        path_str = unquote(path_str)
        return Path(path_str)
    return Path(uri)
