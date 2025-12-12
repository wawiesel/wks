"""Reset database command - clears all documents from a database."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import DatabaseResetOutput
from .Database import Database


def cmd_reset(database: str) -> StageResult:
    """Reset (clear) a database by deleting all documents.

    Args:
        database: Database name (e.g., "monitor", "vault", "transform")

    Returns:
        StageResult with reset operation status
    """
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()

        yield (0.6, "Deleting documents...")
        try:
            with Database(config.database, database) as database_obj:
                deleted_count = database_obj.delete_many({})

            yield (1.0, "Complete")
            result_obj.result = f"Deleted {deleted_count} document(s) from {database}"
            result_obj.output = DatabaseResetOutput(
                errors=[],
                warnings=[],
                database=database,
                deleted_count=deleted_count,
            ).model_dump(mode="python")
            result_obj.success = True
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Reset failed: {e}"
            result_obj.output = DatabaseResetOutput(
                errors=[str(e)],
                warnings=[],
                database=database,
                deleted_count=0,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce=f"Resetting {database} database...",
        progress_callback=do_work,
    )
