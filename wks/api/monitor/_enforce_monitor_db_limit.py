"""Enforce monitor database limits and min_priority."""

from ..db.Database import Database


def _enforce_monitor_db_limit(database: Database, max_docs: int, min_priority: float) -> None:
    """Ensure monitor database does not exceed max_docs and remove entries below min_priority."""
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
        if extras <= 0:
            return

        lowest_priority_docs = database.find({}, {"_id": 1, "priority": 1}).sort("priority", 1).limit(extras)
        ids_to_delete = [doc["_id"] for doc in lowest_priority_docs]
        if ids_to_delete:
            database.delete_many({"_id": {"$in": ids_to_delete}})
    except Exception:
        # Silent on purpose: sync should not crash on enforcement issues
        return
