"""Vault status aggregation for CLI and daemon reporting."""

from __future__ import annotations

__all__ = ["VaultIssue", "VaultStatusSummary", "VaultStatusController"]

from contextlib import contextmanager
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterator, List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection

from ..config import load_config
from .config import VaultDatabaseConfig
from .constants import (
    DOC_TYPE_LINK,
    META_DOCUMENT_ID,
    STATUS_OK,
    STATUS_MISSING_SYMLINK,
    STATUS_MISSING_TARGET,
    STATUS_LEGACY_LINK,
    LINK_TYPE_WIKILINK,
    LINK_TYPE_EMBED,
    LINK_TYPE_MARKDOWN_URL,
)


@dataclass
class VaultIssue:
    note_path: str
    line_number: int
    target_uri: str
    status: str
    source_heading: str
    raw_line: str
    last_updated: Optional[str]


@dataclass
class VaultStatusSummary:
    total_links: int
    ok_links: int
    missing_symlink: int
    missing_target: int
    legacy_links: int
    external_urls: int
    embeds: int
    wiki_links: int
    last_sync: Optional[str]
    notes_scanned: int
    scan_duration_ms: Optional[int]
    issues: List[VaultIssue]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["issues"] = [asdict(issue) for issue in self.issues]
        return data


class VaultStatusController:
    """Read vault link metadata and summarize health."""

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        config = cfg or load_config()
        db_config = VaultDatabaseConfig.from_config(config)
        self.mongo_uri = db_config.mongo_uri
        self.db_name = db_config.db_name
        self.coll_name = db_config.coll_name

    @contextmanager
    def _mongo_connection(self) -> Iterator[Collection]:
        """Context manager for MongoDB connections with automatic cleanup."""
        client = MongoClient(
            self.mongo_uri,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            retryReads=True,
        )
        try:
            yield client[self.db_name][self.coll_name]
        finally:
            client.close()

    def _fetch_or_aggregate_status_counts(self, collection, meta: Dict[str, Any]) -> Dict[str, int]:
        """Fetch status counts from metadata or aggregate from collection."""
        status_counts = meta.get("status_counts")
        if not status_counts:
            status_counts = {
                row["_id"]: row["count"]
                for row in collection.aggregate(
                    [
                        {"$match": {"doc_type": DOC_TYPE_LINK}},
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                    ]
                )
            }
        return status_counts

    def _fetch_or_aggregate_type_counts(self, collection, meta: Dict[str, Any]) -> Dict[str, int]:
        """Fetch type counts from metadata or aggregate from collection."""
        type_counts = meta.get("type_counts")
        if not type_counts:
            type_counts = {
                row["_id"]: row["count"]
                for row in collection.aggregate(
                    [
                        {"$match": {"doc_type": DOC_TYPE_LINK}},
                        {"$group": {"_id": "$link_type", "count": {"$sum": 1}}},
                    ]
                )
            }
        return type_counts

    def _fetch_issues(self, collection, limit: int = 10) -> List[VaultIssue]:
        """Fetch recent non-ok link issues from collection."""
        issues_cursor = collection.find(
            {"doc_type": DOC_TYPE_LINK, "status": {"$ne": STATUS_OK}},
            {
                "from": 1,
                "line_number": 1,
                "to_uri": 1,
                "status": 1,
                "source_heading": 1,
                "raw_line": 1,
                "last_updated": 1,
            },
        ).sort("last_updated", -1).limit(limit)
        return [
            VaultIssue(
                note_path=doc.get("from", ""),
                line_number=doc.get("line_number", 0),
                target_uri=doc.get("to_uri", ""),
                status=doc.get("status", ""),
                source_heading=doc.get("source_heading", ""),
                raw_line=doc.get("raw_line", ""),
                last_updated=doc.get("last_updated"),
            )
            for doc in issues_cursor
        ]

    def summarize(self) -> VaultStatusSummary:
        with self._mongo_connection() as collection:
            meta = collection.find_one({"_id": META_DOCUMENT_ID}) or {}

            status_counts = self._fetch_or_aggregate_status_counts(collection, meta)
            type_counts = self._fetch_or_aggregate_type_counts(collection, meta)

            total_links = sum(status_counts.values())
            ok_links = status_counts.get(STATUS_OK, 0)
            missing_symlink = status_counts.get(STATUS_MISSING_SYMLINK, 0)
            missing_target = status_counts.get(STATUS_MISSING_TARGET, 0)
            legacy_links = status_counts.get(STATUS_LEGACY_LINK, 0)

            issues = self._fetch_issues(collection)

            last_sync = meta.get("last_scan_started_at")
            notes_scanned = meta.get("notes_scanned", 0)
            scan_duration = meta.get("last_scan_duration_ms")
            errors = list(meta.get("errors", []))

        return VaultStatusSummary(
            total_links=total_links,
            ok_links=ok_links,
            missing_symlink=missing_symlink,
            missing_target=missing_target,
            legacy_links=legacy_links,
            external_urls=type_counts.get(LINK_TYPE_MARKDOWN_URL, 0),
            embeds=type_counts.get(LINK_TYPE_EMBED, 0),
            wiki_links=type_counts.get(LINK_TYPE_WIKILINK, 0),
            last_sync=last_sync,
            notes_scanned=notes_scanned,
            scan_duration_ms=scan_duration,
            issues=issues,
            errors=errors,
        )
