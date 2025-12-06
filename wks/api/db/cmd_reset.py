"""Reset database command - clears all documents from a collection."""

from ..base import StageResult
from .DbCollection import DbCollection


def cmd_reset(collection: str) -> StageResult:
    """Reset (clear) a database collection by deleting all documents.

    Args:
        collection: Collection name (e.g., "monitor", "vault", "transform")

    Returns:
        StageResult with reset operation status
    """
    from ...api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()

    try:
        with DbCollection(config.db, collection) as collection_obj:
            deleted_count = collection_obj.delete_many({})

        return StageResult(
            announce=f"Resetting {collection} collection...",
            result=f"Deleted {deleted_count} document(s) from {collection}",
            output={
                "collection": collection,
                "deleted_count": deleted_count,
                "success": True,
            },
            success=True,
        )
    except Exception as e:
        return StageResult(
            announce=f"Resetting {collection} collection...",
            result=f"Reset failed: {e}",
            output={
                "collection": collection,
                "error": str(e),
                "success": False,
            },
            success=False,
        )
