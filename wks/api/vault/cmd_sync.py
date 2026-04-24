import re
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from wks.api.config.expand_paths import expand_paths
from wks.api.config.write_status_file import write_status_file

from ..config._ensure_arg_uri import _ensure_arg_uri
from ..config.StageResult import StageResult
from ..config.URI import URI
from . import VaultSyncOutput

_VAULT_EXTENSIONS = {".md"}


def cmd_sync(uri: URI | None = None, recursive: bool = False) -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        import time

        from ..config.WKSConfig import WKSConfig
        from ..link.cmd_sync import cmd_sync as link_cmd_sync
        from .Vault import Vault

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            vault_cfg = config.vault
            _ = vault_cfg.base_dir
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
                if uri:
                    input_path = _ensure_arg_uri(
                        uri,
                        result_obj,
                        VaultSyncOutput,
                        vault_path=vault_path,
                        uri_field=None,
                        notes_scanned=0,
                        links_written=0,
                        links_deleted=0,
                        sync_duration_ms=0,
                        success=False,
                    )
                    if not input_path:
                        return
                    files = list(expand_paths(input_path, recursive=recursive, extensions=_VAULT_EXTENSIONS))
                else:
                    input_path = vault_path
                    files = list(expand_paths(vault_path, recursive=True, extensions=_VAULT_EXTENSIONS))

                yield (0.4, f"Syncing {len(files)} vault files...")
                total_found = 0
                total_synced = 0
                all_errors: list[str] = []

                for i, file_path in enumerate(files):
                    progress = 0.4 + (0.5 * (i / len(files)))
                    yield (progress, f"Syncing {file_path.name}...")

                    from wks.api.config.URI import URI

                    link_result = link_cmd_sync(URI.from_path(file_path), parser="vault", recursive=False, remote=False)

                    for _ in link_result.progress_callback(link_result):
                        pass

                    if link_result.output:
                        total_found += link_result.output["links_found"]
                        total_synced += link_result.output["links_synced"]
                        if link_result.output.get("errors"):
                            all_errors.extend(link_result.output["errors"])

                yield (0.9, "Pruning deleted files...")
                deleted_count = 0
                processed_uris = set()

                target_path = input_path if uri else vault_path
                if target_path == vault_path:
                    scope_prefix = "vault:///"
                else:
                    scope_prefix = f"vault:///{target_path.relative_to(vault_path)}"

                if not scope_prefix.endswith("/") and target_path.is_dir():
                    scope_prefix += "/"

                for f in files:
                    processed_uris.add(f"vault:///{f.relative_to(vault_path)}")

                from wks.api.database.Database import Database

                with Database(config.database, "edges") as database:
                    if scope_prefix:
                        regex = f"^{re.escape(scope_prefix)}.*\\.md$"
                        cursor = database.find({"from_local_uri": {"$regex": regex}}, {"from_local_uri": 1})

                        db_uris = {doc["from_local_uri"] for doc in cursor}

                        stale = db_uris - processed_uris
                        if stale:
                            deleted_count = database.delete_many({"from_local_uri": {"$in": list(stale)}})

                yield (0.95, "Running backend-specific operations...")

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

    path_info = f" ({uri})" if uri else ""
    announce = f"Syncing vault{path_info}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
