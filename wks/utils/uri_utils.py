"""Path and URI conversion utilities for WKS.

The monitor database stores paths as URIs (file:///...) while configuration
uses regular paths (~/_vault, /Users/ww5/_vault). These utilities handle
conversion between the two forms.

Vault links use vault:/// URIs for paths within the vault and file:/// for
paths outside the vault.
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
    if uri.startswith("file://"):
        # Remove file:// prefix
        path_str = uri[7:]
        # URL decode any percent-encoded characters
        path_str = unquote(path_str)
        return Path(path_str)
    return Path(uri)


def convert_to_uri(path_or_uri: str | Path, vault_path: Path | None = None) -> str:
    """Convert any path or URI to the appropriate URI format.

    This is the central conversion function used throughout WKS for normalizing
    user input to URIs. It handles:
    - Already-formatted URIs (vault:///, file:///) - returns as-is
    - File paths within vault - converts to vault:/// URI
    - File paths outside vault - converts to file:/// URI

    Args:
        path_or_uri: Path string, Path object, or URI string
        vault_path: Optional vault base directory. If None, all paths become file:/// URIs.

    Returns:
        URI string (vault:/// or file:///)

    Examples:
        >>> convert_to_uri("vault:///Projects/2025-WKS.md")
        "vault:///Projects/2025-WKS.md"

        >>> convert_to_uri("~/_vault/Index.md", Path("~/_vault").expanduser())
        "vault:///Index.md"

        >>> convert_to_uri("/Users/ww5/2025-WKS/README.md")
        "file:///Users/ww5/2025-WKS/README.md"
    """
    from .expand_path import expand_path

    # Already a URI - return as-is
    if isinstance(path_or_uri, str) and (path_or_uri.startswith("vault:///") or path_or_uri.startswith("file:///")):
        return path_or_uri

    # Convert to Path and expand
    path = expand_path(path_or_uri) if isinstance(path_or_uri, str) else path_or_uri.expanduser().resolve()

    # If vault_path provided, check if path is within vault
    if vault_path is not None:
        if isinstance(vault_path, str):
            vault_path = Path(vault_path)
        vault_path = vault_path.expanduser().resolve()
        try:
            rel_path = path.relative_to(vault_path)
            # Path is within vault - return vault:/// URI
            return f"vault:///{rel_path}"
        except ValueError:
            # Path is outside vault - fall through to file:/// URI
            pass

    # Default to file:/// URI
    return path_to_uri(path)
