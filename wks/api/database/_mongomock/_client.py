"""Shared mongomock client (UNO: single helper)."""

import mongomock

# Shared mongomock client for all instances (singleton pattern)
_shared_mongomock_client: mongomock.MongoClient | None = None


def _get_mongomock_client() -> mongomock.MongoClient:
    """Get or create shared mongomock client."""
    global _shared_mongomock_client
    if _shared_mongomock_client is None:
        _shared_mongomock_client = mongomock.MongoClient()
    return _shared_mongomock_client
