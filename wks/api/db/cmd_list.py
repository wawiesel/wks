"""List databases command."""

from ..base import StageResult
from .Database import Database


def cmd_list() -> StageResult:
    """List available databases.

    Returns:
        StageResult with list of databases (displayed as table)
    """
    from ..config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    try:
        with Database(config.database, "_") as database_obj:
            collection_names = sorted(database_obj._impl.list_collection_names())  # type: ignore[attr-defined]
    except Exception as e:
        return StageResult(
            announce="Listing databases...",
            result=f"Failed to list databases: {e}",
            output={"error": str(e), "databases": []},
            success=False,
        )

    # Filter and display names without prefix
    collections = []
    for name in collection_names:
        if name.startswith(f"{config.database.prefix}."):
            display_name = name[len(f"{config.database.prefix}."):]
            collections.append({"name": display_name, "full_name": name})
        else:
            collections.append({"name": name, "full_name": name})

    return StageResult(
        announce="Listing databases...",
        result=f"Found {len(collections)} database(s)",
        output={
            "databases": [c["name"] for c in collections],
        },
        success=True,
    )
