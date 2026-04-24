import mongomock

_shared_mongomock_client: mongomock.MongoClient | None = None


def _get_mongomock_client() -> mongomock.MongoClient:
    global _shared_mongomock_client
    if _shared_mongomock_client is None:
        _shared_mongomock_client = mongomock.MongoClient()
    return _shared_mongomock_client
