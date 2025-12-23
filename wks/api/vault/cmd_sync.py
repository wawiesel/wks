"""Vault sync API command.

CLI: wksc vault sync [path] [--recursive]
MCP: wksm_vault_sync

Per spec VAU.3: vault sync delegates to link sync, then runs backend-specific ops.
"""

import re
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from wks.api.config.write_status_file import write_status_file
from wks.utils.expand_paths import expand_paths

from ..StageResult import StageResult
from . import VaultSyncOutput

# Vault only processes markdown files
_VAULT_EXTENSIONS = {".md"}


def cmd_sync(path: str | None = None, recursive: bool = False) -> StageResult:
    """Sync vault links to database.

    Args:
        path: Optional file/directory path to sync. If None, sync entire vault.
        recursive: If True and path is directory, recurse into subdirectories.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        import time

        from ..config.WKSConfig import WKSConfig
        from ..link.cmd_sync import cmd_sync as link_cmd_sync
        from .Vault import Vault

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            vault_cfg = config.vault
            base_dir = vault_cfg.base_dir
            if not base_dir:
                raise ValueError("vault.base_dir not configured")
            wks_home = WKSConfig.get_home_dir()
        except Exception as e:
            result_obj.output = VaultSyncOutput(
                errors=[f"Failed to load config: {e}"],
                warnings=[],
                notes_scanned=0,
                links_written=0,
                links_deleted=0,
                sync_duration_ms=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault sync failed: {e}"
            result_obj.success = False
            return

        yield (0.2, "Initializing vault...")
        try:
            with Vault(vault_cfg) as vault:
                vault_path = vault.vault_path
                started = time.perf_counter()
                _started_iso = datetime.now(timezone.utc).isoformat()

                yield (0.3, "Resolving vault path...")
                # Determine sync scope using vault path resolution
                if path:
                    from wks.utils.resolve_vault_path import VaultPathError, resolve_vault_path

                    try:
                        _uri, input_path = resolve_vault_path(path, vault_path)
                    except VaultPathError as e:
                        result_obj.output = VaultSyncOutput(
                            errors=[str(e)],
                            warnings=[],
                            notes_scanned=0,
                            links_written=0,
                            links_deleted=0,
                            sync_duration_ms=0,
                            success=False,
                        ).model_dump(mode="python")
                        result_obj.result = str(e)
                        result_obj.success = False
                        return
                    # Use resolved path
                    files = list(expand_paths(input_path, recursive=recursive, extensions=_VAULT_EXTENSIONS))
                else:
                    # No path = entire vault (always recursive)
                    files = list(expand_paths(vault_path, recursive=True, extensions=_VAULT_EXTENSIONS))

                # if not files: block removed to allow pruning of deleted files

                yield (0.4, f"Syncing {len(files)} vault files...")
                total_found = 0
                total_synced = 0
                all_errors: list[str] = []

                # Delegate to link sync for each file
                for i, file_path in enumerate(files):
                    progress = 0.4 + (0.5 * (i / len(files)))
                    yield (progress, f"Syncing {file_path.name}...")

                    # Call link sync for this file
                    link_result = link_cmd_sync(str(file_path), parser="vault", recursive=False, remote=False)

                    # Execute the link sync
                    for _ in link_result.progress_callback(link_result):
                        pass

                    if link_result.output:
                        total_found += link_result.output["links_found"]
                        total_synced += link_result.output["links_synced"]
                        if link_result.output.get("errors"):
                            all_errors.extend(link_result.output["errors"])

                yield (0.9, "Pruning deleted files...")
                deleted_count = 0
                # Calculate what we expect to exist based on this run
                processed_uris = set()

                # Determine scope prefix using file URIs
                from ...utils.path_to_uri import path_to_uri

                # scope_prefix is the URI of the sync root
                scope_prefix = path_to_uri(input_path) if path else path_to_uri(vault_path)

                if not scope_prefix.endswith("/") and ((path and input_path.is_dir()) or (not path)):
                    # If it's a directory, ensure trailing slash for regex matching of children
                    scope_prefix += "/"

                # Collect confirmed URIs (as file URIs)
                for f in files:
                    processed_uris.add(path_to_uri(f))

                # Database operations
                from wks.api.database.Database import Database

                with Database(config.database, "edges") as database:
                    if scope_prefix:
                        # Find all matching URIs in DB (limited to .md files as this command only syncs markdown)
                        # We MUST NOT delete non-md links (e.g. .txt, .html) that might be managed by other tools
                        # Query from_local_uri
                        regex = f"^{re.escape(scope_prefix)}.*\\.md$"
                        cursor = database.find({"from_local_uri": {"$regex": regex}}, {"from_local_uri": 1})

                        # Use from_local_uri
                        db_uris = {doc["from_local_uri"] for doc in cursor}

                        stale = db_uris - processed_uris
                        if stale:
                            # Delete using from_local_uri
                            deleted_count = database.delete_many({"from_local_uri": {"$in": list(stale)}})

                yield (0.95, "Running backend-specific operations...")

                # Update meta document in link database with last_sync
                sync_time = datetime.now(timezone.utc).isoformat()
                with Database(config.database, "edges") as database:
                    database.update_one(
                        {"_id": "__meta__"},
                        {"$set": {"_id": "__meta__", "doc_type": "meta", "last_sync": sync_time}},
                        upsert=True,
                    )

                duration_ms = int((time.perf_counter() - started) * 1000)

                result_obj.output = VaultSyncOutput(
                    errors=all_errors,
                    warnings=[],
                    notes_scanned=len(files),
                    links_written=total_synced,
                    links_deleted=deleted_count,
                    sync_duration_ms=duration_ms,
                    success=len(all_errors) == 0,
                ).model_dump(mode="python")
                result_obj.result = f"Synced {len(files)} notes, {total_synced} edges"
                result_obj.success = len(all_errors) == 0

                # Write status file
                status = {
                    "last_sync": sync_time,
                    "links_written": total_synced,
                    "success": len(all_errors) == 0,
                }
                write_status_file(status, wks_home=wks_home, filename="vault.json")

        except Exception as e:
            result_obj.output = VaultSyncOutput(
                errors=[f"Vault sync failed: {e}"],
                warnings=[],
                notes_scanned=0,
                links_written=0,
                links_deleted=0,
                sync_duration_ms=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault sync failed: {e}"
            result_obj.success = False
            return

    path_info = f" ({path})" if path else ""
    announce = f"Syncing vault{path_info}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
