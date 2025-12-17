"""Vault status API command.

CLI: wksc vault status
MCP: wksm_vault_status
"""

from collections.abc import Iterator
from typing import Any

from ..database.Database import Database
from ..StageResult import StageResult
from ..utils._write_status_file import write_status_file
from . import VaultStatusOutput


def cmd_status() -> StageResult:
    """Get vault link health status."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig
        from ._constants import DOC_TYPE_LINK, META_DOCUMENT_ID, STATUS_OK

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            wks_home = WKSConfig.get_home_dir()
            # Compute database name from prefix
            database_name = f"{config.database.prefix}.vault"
        except Exception as e:
            result_obj.output = VaultStatusOutput(
                errors=[f"Failed to load config: {e}"],
                warnings=[],
                database="",
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
            with Database(config.database, database_name) as database:
                # Get metadata document
                meta = database.find_one({"_id": META_DOCUMENT_ID}) or {}

                # Get status counts
                yield (0.5, "Aggregating link statistics...")
                status_counts = meta.get("status_counts") or {}
                if not status_counts:
                    # Count by querying
                    all_links = list(database.find({"doc_type": DOC_TYPE_LINK}, {"status": 1}))
                    status_counts = {}
                    for doc in all_links:
                        status = doc.get("status", "unknown")
                        status_counts[status] = status_counts.get(status, 0) + 1

                total_links = sum(status_counts.values())
                ok_links = status_counts.get(STATUS_OK, 0)
                broken_links = total_links - ok_links

                # Get recent issues
                yield (0.7, "Fetching issues...")
                issues_cursor = database.find(
                    {"doc_type": DOC_TYPE_LINK, "status": {"$ne": STATUS_OK}},
                    {"from_uri": 1, "line_number": 1, "to_uri": 1, "status": 1},
                )
                issues = [
                    {
                        "note_path": (doc.get("from_uri", "") or "").replace("vault:///", ""),
                        "line_number": doc.get("line_number", 0),
                        "target_uri": doc.get("to_uri", ""),
                        "status": doc.get("status", ""),
                    }
                    for doc in list(issues_cursor)[:10]  # Limit to 10
                ]

            yield (1.0, "Complete")
            output = VaultStatusOutput(
                errors=[],
                warnings=[],
                database=database_name,
                total_links=total_links,
                ok_links=ok_links,
                broken_links=broken_links,
                issues=issues,
                last_sync=meta.get("last_scan_started_at"),
                notes_scanned=meta.get("notes_scanned", 0),
                success=True,
            ).model_dump(mode="python")

            # Write status file
            write_status_file(output, wks_home=wks_home, filename="vault.json")

            result_obj.output = output
            result_obj.result = f"Vault status: {total_links} links ({broken_links} broken)"
            result_obj.success = True

        except Exception as e:
            result_obj.output = VaultStatusOutput(
                errors=[f"Database query failed: {e}"],
                warnings=[],
                database=database_name,
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
