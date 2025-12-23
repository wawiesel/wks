"""Enforce monitor database limits and min_priority."""

from ..database.Database import Database


def _enforce_monitor_db_limit(
    database: Database, max_docs: int, min_priority: float, warnings: list[str] | None = None
) -> None:
    """Ensure monitor database does not exceed max_docs and remove entries below min_priority.

    Args:
        database: Database instance to enforce limits on
        max_docs: Maximum number of documents to keep (0 = no limit)
        min_priority: Minimum priority threshold (documents below are removed)
        warnings: Optional list to append warning messages to
    """
    try:
        # First, remove entries below min_priority
        if min_priority > 0.0:
            database.delete_many({"priority": {"$lt": min_priority}})

        # Then enforce max_docs limit
        if max_docs <= 0:
            return

        count = database.count_documents({})
        if count <= max_docs:
            return

        extras = count - max_docs

        lowest_priority_docs = database.find({}, {"_id": 1, "priority": 1}).sort("priority", 1).limit(extras)
        ids_to_delete = [doc["_id"] for doc in lowest_priority_docs]
        if ids_to_delete:
            database.delete_many({"_id": {"$in": ids_to_delete}})
    except Exception as e:
        # Report warning but don't crash sync operation
        if warnings is not None:
            warnings.append(f"Database limit enforcement failed: {e}")
