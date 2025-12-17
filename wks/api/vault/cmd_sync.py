"""Vault sync API command.

CLI: wksc vault sync [path]
MCP: wksm_vault_sync
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..StageResult import StageResult
from . import VaultSyncOutput


def cmd_sync(path: str | None = None) -> StageResult:
    """Sync vault links to database.

    Args:
        path: Optional file path to sync. If None, sync entire vault.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ...utils import expand_path
        from ..config.WKSConfig import WKSConfig
        from .indexer import VaultLinkIndexer
        from .obsidian import ObsidianVault

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
            indexer = VaultLinkIndexer.from_config(vault, config)
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
            # If path specified, validate it exists
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
                # Note: path-specific sync not yet implemented, sync entire vault
            result = indexer.sync(batch_size=1000, incremental=False)

            yield (1.0, "Complete")
            result_obj.output = VaultSyncOutput(
                errors=result.stats.errors,
                warnings=[],
                notes_scanned=result.stats.notes_scanned,
                edges_written=result.upserts,
                edges_deleted=result.deleted_records,
                sync_duration_ms=result.sync_duration_ms,
                success=len(result.stats.errors) == 0,
            ).model_dump(mode="python")
            result_obj.result = f"Synced {result.stats.notes_scanned} notes, {result.upserts} edges"
            result_obj.success = len(result.stats.errors) == 0

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
