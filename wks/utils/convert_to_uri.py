from pathlib import Path

from wks.api.URI import URI

from .path_to_uri import path_to_uri


def convert_to_uri(path_or_uri: str | Path | URI, vault_path: Path | None = None) -> URI:
    """Convert any path or URI to a URI object.

    This is the central conversion function used throughout WKS for normalizing
    user input to URIs. It handles:
    - Already-formatted URIs (vault:///, file:///) - returns URI object
    - URI objects - returns as-is
    - File paths within vault - converts to vault:/// URI
    - File paths outside vault - converts to file:/// URI

    Args:
        path_or_uri: Path string, Path object, URI string, or URI object
        vault_path: Optional vault base directory. If None, all paths become file:/// URIs.

    Returns:
        URI object (vault:/// or file:///)

    Examples:
        >>> convert_to_uri("vault:///Projects/2025-WKS.md")
        URI('vault:///Projects/2025-WKS.md')

        >>> convert_to_uri("~/_vault/Index.md", Path("~/_vault").expanduser())
        URI('vault:///Index.md')

        >>> convert_to_uri("/Users/ww5/2025-WKS/README.md")
        URI('file://hostname/Users/ww5/2025-WKS/README.md')
    """
    from wks.utils.normalize_path import normalize_path

    # Already a URI object - return as-is
    if isinstance(path_or_uri, URI):
        return path_or_uri

    # Already a URI string - convert to URI object
    if isinstance(path_or_uri, str) and (path_or_uri.startswith("vault:///") or path_or_uri.startswith("file://")):
        return URI(path_or_uri)

    # Convert to Path and expand
    path = normalize_path(path_or_uri)

    # If vault_path provided, check if path is within vault
    if vault_path is not None:
        vault_path = normalize_path(vault_path)
        try:
            rel_path = path.relative_to(vault_path)
            # Path is within vault - return vault:/// URI
            return URI(f"vault:///{rel_path}")
        except ValueError:
            # Path is outside vault - fall through to file:/// URI
            pass

    # Default to file:/// URI
    return URI(path_to_uri(path))
