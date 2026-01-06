"""Get WKS package version (cached)."""

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

# Package version - cached for performance
_VERSION_CACHE = None


def get_package_version() -> str:
    """Get WKS package version (cached)."""
    global _VERSION_CACHE
    if _VERSION_CACHE is None:
        try:
            _VERSION_CACHE = importlib_metadata.version("wks")
        except Exception:
            _VERSION_CACHE = "unknown"
    return _VERSION_CACHE
