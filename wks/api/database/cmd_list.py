"""List databases command."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import DatabaseListOutput
from .Database import Database


def cmd_list() -> StageResult:
    """List available databases.

    Returns:
        StageResult with list of databases (displayed as table)
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        try:
            config = WKSConfig.load()
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = str(e)
            result_obj.output = DatabaseListOutput(
                errors=[str(e)],
                warnings=[],
                databases=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.5, "Querying database...")
        try:
            database_names = Database.list_databases(config.database)
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Failed to list databases: {e}"
            result_obj.output = DatabaseListOutput(
                errors=[str(e)],
                warnings=[],
                databases=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.8, "Processing database names...")

        yield (1.0, "Complete")
        result_obj.result = f"Found {len(database_names)} database(s)"
        result_obj.output = DatabaseListOutput(
            errors=[],
            warnings=[],
            databases=database_names,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Listing databases...",
        progress_callback=do_work,
    )
