"""Private helper for resolving CLI arguments to URIs."""

from pathlib import Path

from wks.api.config.URI import URI


def _resolve_uri_arg(value: str) -> URI:
    """Resolve CLI argument to strict URI."""
    try:
        return URI(value)
    except ValueError:
        # Not a valid URI, try as path
        p = Path(value)
        # We delegate existence check to API
        return URI.from_path(p.expanduser().absolute())
