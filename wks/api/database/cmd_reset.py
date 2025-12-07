"""Reset database command - clears all documents from a database."""

from collections.abc import Callable

from ..base import StageResult
from .Database import Database


def cmd_reset(database: str) -> StageResult:
    """Reset (clear) a database by deleting all documents.

    Args:
        database: Database name (e.g., "monitor", "vault", "transform")

    Returns:
        StageResult with reset operation status
    """
    def do_work(update_progress: Callable[[str, float], None], result_obj: StageResult) -> None:
        """Do the actual work - called by wrapper after announce is displayed."""
        from ..config.WKSConfig import WKSConfig

        update_progress("Loading configuration...", 0.2)
        config = WKSConfig.load()

        update_progress("Deleting documents...", 0.6)
        try:
            with Database(config.database, database) as database_obj:
                deleted_count = database_obj.delete_many({})

            update_progress("Complete", 1.0)
            result_obj.result = f"Deleted {deleted_count} document(s) from {database}"
            result_obj.output = {
                "database": database,
                "deleted_count": deleted_count,
            }
            result_obj.success = True
        except Exception as e:
            update_progress("Complete", 1.0)
            result_obj.result = f"Reset failed: {e}"
            result_obj.output = {
                "database": database,
                "error": str(e),
            }
            result_obj.success = False

    return StageResult(
        announce=f"Resetting {database} database...",
        progress_callback=do_work,
        progress_total=1,
    )
