"""Reset database command - clears all documents from a database."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import DatabaseResetOutput
from .Database import Database


def cmd_reset(database: str) -> StageResult:
    """Reset (clear) a database by deleting all documents.

    Args:
        database: Database name (e.g., "monitor", "vault", "transform") or "all"

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

        targets = Database.list_databases(config.database) if database == "all" else [database]

        total_deleted = 0
        deleted_details = []
        errors = []

        yield (0.4, f"Resetting {len(targets)} databases...")

        for i, target_db in enumerate(targets):
            progress_base = 0.4 + (0.5 * (i / len(targets)))
            yield (progress_base, f"Clearing {target_db}...")

            try:
                with Database(config.database, target_db) as database_obj:
                    count = database_obj.delete_many({})
                    total_deleted += count
                    deleted_details.append(f"{target_db}: {count}")
            except Exception as e:
                errors.append(f"Failed to reset {target_db}: {e}")

        yield (1.0, "Complete")

        if errors:
            result_obj.success = False
            result_obj.result = f"Reset completed with errors. Deleted {total_deleted}. Errors: {'; '.join(errors)}"
        else:
            result_obj.success = True
            result_obj.result = f"Deleted {total_deleted} document(s) from {database} ({', '.join(deleted_details)})"

        result_obj.output = DatabaseResetOutput(
            errors=errors,
            warnings=[],
            database=database,
            deleted_count=total_deleted,
        ).model_dump(mode="python")

    return StageResult(
        announce=f"Resetting {database} database...",
        progress_callback=do_work,
    )
