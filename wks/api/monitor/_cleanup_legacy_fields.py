"""Cleanup legacy fields from monitor database documents."""

from ..database.Database import Database


def _cleanup_legacy_fields(database: Database) -> None:
    """Remove legacy fields that are no longer in the spec.

    Currently removes:
    - touches_per_day (legacy field, not in monitor spec)
    """
    try:
        # Remove touches_per_day from all documents
        database.update_many({}, {"$unset": {"touches_per_day": ""}})
    except Exception:
        # Silent on purpose: cleanup should not crash sync
        pass
