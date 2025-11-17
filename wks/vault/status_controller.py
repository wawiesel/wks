"""Vault status aggregation for CLI and daemon reporting."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from ..db_helpers import parse_database_key
from ..config import load_config


@dataclass
class VaultIssue:
    note_path: str
    line_number: int
    target_uri: str
    status: str
    source_heading: str
    raw_line: str
    links_rel: str
    resolved_path: str
    resolved_exists: bool
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
        db_cfg = config.get("db")
        if not db_cfg or not db_cfg.get("uri"):
            raise KeyError("db.uri is required in config (found: missing, expected: MongoDB connection URI string)")
        vault_cfg = config.get("vault")
        if not vault_cfg or not vault_cfg.get("database"):
            raise KeyError("vault.database is required in config (found: missing, expected: 'database.collection')")
        db_name, coll_name = parse_database_key(vault_cfg["database"])
        self.mongo_uri = db_cfg["uri"]
        self.db_name = db_name
        self.coll_name = coll_name

    def summarize(self) -> VaultStatusSummary:
        client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
        collection = client[self.db_name][self.coll_name]
        meta = collection.find_one({"_id": "__meta__"}) or {}

        status_counts = meta.get("status_counts")
        if not status_counts:
            status_counts = {
                row["_id"]: row["count"]
                for row in collection.aggregate(
                    [
                        {"$match": {"doc_type": "link"}},
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                    ]
                )
            }
        type_counts = meta.get("type_counts")
        if not type_counts:
            type_counts = {
                row["_id"]: row["count"]
                for row in collection.aggregate(
                    [
                        {"$match": {"doc_type": "link"}},
                        {"$group": {"_id": "$link_type", "count": {"$sum": 1}}},
                    ]
                )
            }

        total_links = sum(status_counts.values())
        ok_links = status_counts.get("ok", 0)
        missing_symlink = status_counts.get("missing_symlink", 0)
        missing_target = status_counts.get("missing_target", 0)
        legacy_links = status_counts.get("legacy_link", 0)

        issues_cursor = collection.find(
            {"doc_type": "link", "status": {"$ne": "ok"}},
            {
                "note_path": 1,
                "line_number": 1,
                "target_uri": 1,
                "status": 1,
                "source_heading": 1,
                "raw_line": 1,
                "links_rel": 1,
                "resolved_path": 1,
                "resolved_exists": 1,
                "last_updated": 1,
            },
        ).sort("last_updated", -1).limit(10)
        issues = [
            VaultIssue(
                note_path=doc.get("note_path", ""),
                line_number=doc.get("line_number", 0),
                target_uri=doc.get("target_uri", ""),
                status=doc.get("status", ""),
                source_heading=doc.get("source_heading", ""),
                raw_line=doc.get("raw_line", ""),
                links_rel=doc.get("links_rel", ""),
                resolved_path=doc.get("resolved_path", ""),
                resolved_exists=bool(doc.get("resolved_exists", False)),
                last_updated=doc.get("last_updated"),
            )
            for doc in issues_cursor
        ]
        client.close()

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
            external_urls=type_counts.get("markdown_url", 0),
            embeds=type_counts.get("embed", 0),
            wiki_links=type_counts.get("wikilink", 0),
            last_sync=last_sync,
            notes_scanned=notes_scanned,
            scan_duration_ms=scan_duration,
            issues=issues,
            errors=errors,
        )
