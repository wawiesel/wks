"""Helper function for converting URI objects to strings."""

from wks.api.URI import URI


def uri_to_string(uri: URI | str) -> str:
    """Convert URI object or string to string.

    Args:
        uri: URI object or string

    Returns:
        String representation of the URI
    """
    return str(uri) if isinstance(uri, URI) else uri
