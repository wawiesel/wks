"""Vault sync API command.

CLI: wksc vault sync [path]
MCP: wksm_vault_sync
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..database.Database import Database
from ..StageResult import StageResult
from . import VaultSyncOutput


def cmd_sync(path: str | None = None) -> StageResult:
    """Sync vault links to database.

    Args:
        path: Optional file path to sync. If None, sync entire vault.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        import time

        from ...utils import expand_path
        from ..config.WKSConfig import WKSConfig
        from ._constants import DOC_TYPE_LINK, META_DOCUMENT_ID
        from ._obsidian._Impl import _Impl as ObsidianVault
        from ._obsidian._Scanner import _Scanner

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            base_dir = config.vault.base_dir
            if not base_dir:
                raise ValueError("vault.base_dir not configured")
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
            vault = ObsidianVault(expand_path(base_dir))
            scanner = _Scanner(vault)
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

        yield (0.3, "Scanning vault for links...")
        try:
            started = time.perf_counter()
            started_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

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
            with Database(config.database, config.vault.database) as database:
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

        except Exception as e:
            result_obj.output = VaultSyncOutput(
                errors=[f"Sync failed: {e}"],
                warnings=[],
                notes_scanned=0,
                edges_written=0,
                edges_deleted=0,
                sync_duration_ms=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault sync failed: {e}"
            result_obj.success = False

    announce = f"Syncing vault{f' ({path})' if path else ''}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
