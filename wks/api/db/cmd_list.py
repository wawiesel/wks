"""List database collections command."""

from ..base import StageResult
from .DbCollection import DbCollection


def cmd_list() -> StageResult:
    """List available database collections.

    Returns:
        StageResult with list of collections (displayed as table)
    """
    from ...api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    try:
        with DbCollection(config.db, "_") as collection_obj:
            collection_names = sorted(collection_obj._impl.list_collection_names())  # type: ignore[attr-defined]
    except Exception as e:
        return StageResult(
            announce="Listing collections...",
            result=f"Failed to list collections: {e}",
            output={"error": str(e), "collections": []},
            success=False,
        )

    # Filter and display names without prefix
    collections = []
    for name in collection_names:
        if name.startswith(f"{config.db.prefix}."):
            display_name = name[len(f"{config.db.prefix}."):]
            collections.append({"name": display_name, "full_name": name})
        else:
            collections.append({"name": name, "full_name": name})

    return StageResult(
        announce="Listing collections...",
        result=f"Found {len(collections)} collection(s)",
        output={
            "collections": [c["name"] for c in collections],
        },
        success=True,
    )
