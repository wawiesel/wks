from ..database.Database import Database


def _enforce_monitor_db_limit(
    database: Database, max_docs: int, min_priority: float, warnings: list[str] | None = None
) -> None:
    try:
        if min_priority > 0.0:
            database.delete_many({"priority": {"$lt": min_priority}})

        if max_docs <= 0:
            return

        query = {"doc_type": {"$ne": "meta"}}

        count = database.count_documents(query)
        if count <= max_docs:
            return

        extras = count - max_docs

        lowest_priority_docs = database.find(query, {"_id": 1, "priority": 1}).sort("priority", 1).limit(extras)
        ids_to_delete = [doc["_id"] for doc in lowest_priority_docs]
        if ids_to_delete:
            database.delete_many({"_id": {"$in": ids_to_delete}})
    except Exception as e:
        if warnings is not None:
            warnings.append(f"Database limit enforcement failed: {e}")
