"""Reset database command - clears all documents from a database."""

from ..base import StageResult
from .Database import Database


def cmd_reset(database: str) -> StageResult:
    """Reset (clear) a database by deleting all documents.

    Args:
        database: Database name (e.g., "monitor", "vault", "transform")

    Returns:
        StageResult with reset operation status
    """
    from ..config.WKSConfig import WKSConfig

    config = WKSConfig.load()

    try:
        with Database(config.database, database) as database_obj:
            deleted_count = database_obj.delete_many({})

        return StageResult(
            announce=f"Resetting {database} database...",
            result=f"Deleted {deleted_count} document(s) from {database}",
            output={
                "database": database,
                "deleted_count": deleted_count,
                "success": True,
            },
            success=True,
        )
    except Exception as e:
        return StageResult(
            announce=f"Resetting {database} database...",
            result=f"Reset failed: {e}",
            output={
                "database": database,
                "error": str(e),
                "success": False,
            },
            success=False,
        )
