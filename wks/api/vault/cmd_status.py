"""Vault status API command.

CLI: wksc vault status
MCP: wksm_vault_status
"""

from collections.abc import Iterator
from typing import Any

from ..StageResult import StageResult
from . import VaultStatusOutput


def cmd_status() -> StageResult:
    """Get vault link health status."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from pymongo import MongoClient

        from ..config.WKSConfig import WKSConfig
        from ..database._mongo._DbConfigData import _DbConfigData as _MongoDbConfigData
        from .constants import DOC_TYPE_LINK, META_DOCUMENT_ID, STATUS_OK

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            if isinstance(config.database.data, _MongoDbConfigData):
                mongo_uri = config.database.data.uri
            else:
                result_obj.output = VaultStatusOutput(
                    errors=[f"Vault requires mongo backend, got {config.database.type}"],
                    warnings=[],
                    total_links=0,
                    ok_links=0,
                    broken_links=0,
                    issues=[],
                    last_sync=None,
                    notes_scanned=0,
                    success=False,
                ).model_dump(mode="python")
                result_obj.result = "Vault status failed: unsupported database backend"
                result_obj.success = False
                return

            db_name, coll_name = config.vault.database.split(".", 1)
        except Exception as e:
            result_obj.output = VaultStatusOutput(
                errors=[f"Failed to load config: {e}"],
                warnings=[],
                total_links=0,
                ok_links=0,
                broken_links=0,
                issues=[],
                last_sync=None,
                notes_scanned=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault status failed: {e}"
            result_obj.success = False
            return

        yield (0.3, "Querying vault database...")
        try:
            client: MongoClient = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
            )
            collection = client[db_name][coll_name]

            # Get metadata document
            meta = collection.find_one({"_id": META_DOCUMENT_ID}) or {}

            # Get status counts
            yield (0.5, "Aggregating link statistics...")
            status_counts = meta.get("status_counts") or {}
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

            total_links = sum(status_counts.values())
            ok_links = status_counts.get(STATUS_OK, 0)
            broken_links = total_links - ok_links

            # Get recent issues
            yield (0.7, "Fetching issues...")
            issues_cursor = (
                collection.find(
                    {"doc_type": DOC_TYPE_LINK, "status": {"$ne": STATUS_OK}},
                    {"from_uri": 1, "line_number": 1, "to_uri": 1, "status": 1},
                )
                .sort("last_updated", -1)
                .limit(10)
            )
            issues = [
                {
                    "note_path": (doc.get("from_uri", "") or "").replace("vault:///", ""),
                    "line_number": doc.get("line_number", 0),
                    "target_uri": doc.get("to_uri", ""),
                    "status": doc.get("status", ""),
                }
                for doc in issues_cursor
            ]

            client.close()

            yield (1.0, "Complete")
            result_obj.output = VaultStatusOutput(
                errors=[],
                warnings=[],
                total_links=total_links,
                ok_links=ok_links,
                broken_links=broken_links,
                issues=issues,
                last_sync=meta.get("last_scan_started_at"),
                notes_scanned=meta.get("notes_scanned", 0),
                success=True,
            ).model_dump(mode="python")
            result_obj.result = f"Vault status: {total_links} links ({broken_links} broken)"
            result_obj.success = True

        except Exception as e:
            result_obj.output = VaultStatusOutput(
                errors=[f"Database query failed: {e}"],
                warnings=[],
                total_links=0,
                ok_links=0,
                broken_links=0,
                issues=[],
                last_sync=None,
                notes_scanned=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault status failed: {e}"
            result_obj.success = False

    return StageResult(
        announce="Checking vault status...",
        progress_callback=do_work,
    )
