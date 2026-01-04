"""Link sync API command."""

from collections.abc import Iterator
from typing import Any

from wks.utils.expand_paths import expand_paths

from .._ensure_arg_uri import _ensure_arg_uri
from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from ..URI import URI
from ..vault.Vault import Vault
from . import LinkSyncOutput
from ._sync_single_file import _sync_single_file

# Supported extensions for link parsing
_LINK_EXTENSIONS = {".md", ".html", ".htm", ".rst", ".txt"}


def cmd_sync(
    uri: URI,
    parser: str | None = None,
    recursive: bool = False,
    remote: bool = False,
) -> StageResult:
    """Sync file/directory links to database if monitored."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        vault_cfg = config.vault

        yield (0.2, "Resolving path...")
        input_path = _ensure_arg_uri(
            uri,
            result_obj,
            LinkSyncOutput,
            is_monitored=False,
            links_found=0,
            links_synced=0,
        )
        if not input_path:
            return

        yield (0.3, "Expanding paths...")
        try:
            files = list(expand_paths(input_path, recursive=recursive, extensions=_LINK_EXTENSIONS))
        except FileNotFoundError as e:
            result_obj.output = LinkSyncOutput(
                path=str(input_path),
                is_monitored=False,
                links_found=0,
                links_synced=0,
                errors=[str(e)],
            ).model_dump(mode="python")
            result_obj.result = f"Error: {e}"
            result_obj.success = False
            return

        if not files:
            result_obj.output = LinkSyncOutput(
                path=str(input_path),
                is_monitored=True,
                links_found=0,
                links_synced=0,
                errors=["No matching files found"],
            ).model_dump(mode="python")
            result_obj.result = "No files to sync"
            result_obj.success = True
            return

        yield (0.4, "Initializing resolver...")
        # Keep vault open for duration of sync
        try:
            with Vault(vault_cfg) as vault:
                # We reuse the vault's resolve_link for all files
                resolver_func = vault.resolve_link
                vault_root = vault.vault_path

                yield (0.5, f"Syncing {len(files)} files...")
                total_found = 0
                total_synced = 0
                all_errors: list[str] = []

                for i, file_path in enumerate(files):
                    progress = 0.5 + (0.4 * (i / len(files)))
                    yield (progress, f"Syncing {file_path.name}...")

                    found, synced, errors = _sync_single_file(
                        file_path, parser, remote, config, resolver_func, vault_root
                    )
                    total_found += found
                    total_synced += synced
                    all_errors.extend(errors)

        except Exception:
            # Fallback if vault fails (e.g. no config)
            # Sync without vault context
            yield (0.5, f"Syncing {len(files)} files (no vault)...")
            total_found = 0
            total_synced = 0
            all_errors = []

            for i, file_path in enumerate(files):
                progress = 0.5 + (0.4 * (i / len(files)))
                yield (progress, f"Syncing {file_path.name}...")

                found, synced, errors = _sync_single_file(file_path, parser, remote, config, None, None)
                total_found += found
                total_synced += synced
                all_errors.extend(errors)

        result_obj.output = LinkSyncOutput(
            path=str(input_path),
            is_monitored=True,
            links_found=total_found,
            links_synced=total_synced,
            errors=all_errors,
        ).model_dump(mode="python")

        file_word = "file" if len(files) == 1 else "files"
        result_obj.result = f"Synced {total_synced} links from {len(files)} {file_word}"
        result_obj.success = True

    return StageResult(announce=f"Syncing links for {uri}...", progress_callback=do_work)
