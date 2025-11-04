"""
Database compatibility helpers.

We persist a tiny metadata document inside each Mongo database so upgrades
can detect whether an existing dataset is compatible with the current CLI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple, Any

SPACE_COMPAT_DEFAULT = "space-v1"
TIME_COMPAT_DEFAULT = "time-v1"
META_COLLECTION = "_wks_meta"
_SCOPE_KEYS = {
    "space": "mongo.compatibility.space",
    "time": "mongo.compatibility.time",
}


class IncompatibleDatabase(RuntimeError):
    """Raised when the stored compatibility tag does not match expectations."""

    def __init__(self, scope: str, stored_tag: str, expected_tag: str):
        config_key = _SCOPE_KEYS.get(scope, f"mongo.compatibility.{scope}")
        message = (
            f"Incompatible {scope} database: stored compatibility tag '{stored_tag or '?'}' "
            f"does not match expected '{expected_tag}'. "
            f"Update {config_key} in ~/.wks/config.json to '{stored_tag}' to reuse the existing data, "
            "or run `wkso db reset` to rebuild the database."
        )
        super().__init__(message)
        self.scope = scope
        self.stored_tag = stored_tag
        self.expected_tag = expected_tag


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_tag(value: Any, default: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return default


def resolve_db_compatibility(cfg: Dict[str, Any]) -> Tuple[str, str]:
    """Return (space_tag, time_tag) strings using config overrides when present."""
    compat_cfg = (cfg.get("mongo") or {}).get("compatibility") or {}
    space_tag = _normalize_tag(compat_cfg.get("space"), SPACE_COMPAT_DEFAULT)
    time_tag = _normalize_tag(compat_cfg.get("time"), TIME_COMPAT_DEFAULT)
    return space_tag, time_tag


def ensure_db_compat(
    client,
    database_name: str,
    scope: str,
    expected_tag: str,
    *,
    product_version: str | None = None,
) -> str:
    """
    Ensure the given database stores the expected compatibility tag.

    Returns the stored tag (which matches expected_tag) or raises IncompatibleDatabase.
    """
    db = client[database_name]
    meta = db[META_COLLECTION]
    now = _utc_now()
    doc = meta.find_one({"_id": scope})
    if doc is None:
        meta.replace_one(
            {"_id": scope},
            {
                "compat_tag": expected_tag,
                "created_at": now,
                "last_used_at": now,
                "product_version": product_version,
            },
            upsert=True,
        )
        return expected_tag
    stored_tag = _normalize_tag(doc.get("compat_tag"), "")
    if stored_tag != expected_tag:
        raise IncompatibleDatabase(scope, stored_tag, expected_tag)
    meta.update_one(
        {"_id": scope},
        {
            "$set": {
                "last_used_at": now,
                "product_version": product_version or doc.get("product_version"),
            }
        },
    )
    return stored_tag

