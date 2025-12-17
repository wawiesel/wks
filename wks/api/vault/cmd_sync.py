"""Vault sync API command.

CLI: wksc vault sync [path]
MCP: wksm_vault_sync
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..database.Database import Database
from ..StageResult import StageResult
from ..utils._write_status_file import write_status_file
from . import VaultSyncOutput


def cmd_sync(path: str | None = None) -> StageResult:
    """Sync vault links to database.

    Args:
        path: Optional file path to sync. If None, sync entire vault.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        import time

        from ..config.WKSConfig import WKSConfig
        from ._constants import DOC_TYPE_LINK, META_DOCUMENT_ID
        from ._obsidian._Scanner import _Scanner
        from .Vault import Vault

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            base_dir = config.vault.base_dir
            if not base_dir:
                raise ValueError("vault.base_dir not configured")
            wks_home = WKSConfig.get_home_dir()
            # Compute database name from prefix
            database_name = f"{config.database.prefix}.vault"
        except Exception as e:
            result_obj.output = VaultSyncOutput(
                errors=[f"Failed to load config: {e}"],
                warnings=[],
                notes_scanned=0,
                edges_written=0,
                edges_deleted=0,
                sync_duration_ms=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault sync failed: {e}"
            result_obj.success = False
            return

        yield (0.2, "Initializing vault...")
        try:
            # Vault acts as a context manager and facade
            with Vault(config.vault) as vault:
                scanner = _Scanner(vault)

                yield (0.3, "Scanning vault for links...")
                try:
                    started = time.perf_counter()
                    started_iso = datetime.now(timezone.utc).isoformat()

                    # If path specified, validate it exists
                    files_to_scan = None
                    if path:
                        file_path = Path(path).expanduser().resolve()
                        if not file_path.exists():
                            result_obj.output = VaultSyncOutput(
                                errors=[f"File not found: {path}"],
                                warnings=[],
                                notes_scanned=0,
                                edges_written=0,
                                edges_deleted=0,
                                sync_duration_ms=0,
                                success=False,
                            ).model_dump(mode="python")
                            result_obj.result = "Vault sync failed: file not found"
                            result_obj.success = False
                            return
                        files_to_scan = [file_path]

                    records = scanner.scan(files=files_to_scan)
                    stats = scanner.stats

                    yield (0.5, "Writing to database...")
                    total_upserts = 0
                    with Database(config.database, database_name) as database:
                        for record in records:
                            doc = record.to_document(seen_at_iso=started_iso)
                            database.update_one(
                                {"_id": record.identity},
                                {
                                    "$set": doc,
                                    "$setOnInsert": {"first_seen": started_iso},
                                },
                                upsert=True,
                            )
                            total_upserts += 1

                        # Delete stale links
                        yield (0.8, "Cleaning stale links...")
                        deleted = database.delete_many(
                            {
                                "doc_type": DOC_TYPE_LINK,
                                "last_seen": {"$lt": started_iso},
                            }
                        )

                        # Update meta document
                        meta_doc = {
                            "_id": META_DOCUMENT_ID,
                            "doc_type": "meta",
                            "last_scan_started_at": started_iso,
                            "last_scan_duration_ms": int((time.perf_counter() - started) * 1000),
                            "notes_scanned": stats.notes_scanned,
                            "edges_written": stats.edge_total,
                        }
                        database.update_one({"_id": META_DOCUMENT_ID}, {"$set": meta_doc}, upsert=True)

                    yield (1.0, "Complete")
                    result_obj.output = VaultSyncOutput(
                        errors=stats.errors,
                        warnings=[],
                        notes_scanned=stats.notes_scanned,
                        edges_written=total_upserts,
                        edges_deleted=deleted,
                        sync_duration_ms=int((time.perf_counter() - started) * 1000),
                        success=len(stats.errors) == 0,
                    ).model_dump(mode="python")
                    result_obj.result = f"Synced {stats.notes_scanned} notes, {total_upserts} edges"
                    result_obj.success = len(stats.errors) == 0

                    # Write status file after sync
                    status = {
                        "database": database_name,
                        "last_sync": datetime.now(timezone.utc).isoformat(),
                        "notes_scanned": stats.notes_scanned,
                        "edges_written": total_upserts,
                        "edges_deleted": deleted,
                        "success": len(stats.errors) == 0,
                    }
                    write_status_file(status, wks_home=wks_home, filename="vault.json")

                except Exception as e:
                    # Inner exception (scanning/syncing)
                    raise e

        except Exception as e:
            result_obj.output = VaultSyncOutput(
                errors=[f"Failed to initialize vault: {e}"],
                warnings=[],
                notes_scanned=0,
                edges_written=0,
                edges_deleted=0,
                sync_duration_ms=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault sync failed: {e}"
            result_obj.success = False
            return

    announce = f"Syncing vault{f' ({path})' if path else ''}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
