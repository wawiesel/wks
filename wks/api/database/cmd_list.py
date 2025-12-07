"""List databases command."""

from collections.abc import Callable

from ..base import StageResult
from .Database import Database


def cmd_list() -> StageResult:
    """List available databases.

    Returns:
        StageResult with list of databases (displayed as table)
    """
    def do_work(update_progress: Callable[[str, float], None], result_obj: StageResult) -> None:
        """Do the actual work - called by wrapper after announce is displayed."""
        from ..config.WKSConfig import WKSConfig

        update_progress("Loading configuration...", 0.2)
        config = WKSConfig.load()
        
        update_progress("Querying database...", 0.5)
        try:
            with Database(config.database, "_") as database_obj:
                collection_names = sorted(database_obj._impl.list_collection_names())  # type: ignore[attr-defined]
        except Exception as e:
            update_progress("Complete", 1.0)
            result_obj.result = f"Failed to list databases: {e}"
            result_obj.output = {"error": str(e), "databases": []}
            result_obj.success = False
            return

        # Filter and display names without prefix
        update_progress("Processing collection names...", 0.8)
        collections = []
        for name in collection_names:
            if name.startswith(f"{config.database.prefix}."):
                display_name = name[len(f"{config.database.prefix}."):]
                collections.append({"name": display_name, "full_name": name})
            else:
                collections.append({"name": name, "full_name": name})

        update_progress("Complete", 1.0)
        result_obj.result = f"Found {len(collections)} database(s)"
        result_obj.output = {
            "databases": [c["name"] for c in collections],
        }
        result_obj.success = True

    return StageResult(
        announce="Listing databases...",
        progress_callback=do_work,
        progress_total=1,
    )
