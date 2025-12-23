"""Link sync API command."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from wks.utils.expand_paths import expand_paths

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from ..vault._obsidian.LinkResolver import LinkResolver
from ..vault.Vault import Vault
from . import LinkSyncOutput
from ._sync_single_file import _sync_single_file

# Supported extensions for link parsing
_LINK_EXTENSIONS = {".md", ".html", ".htm", ".rst", ".txt"}


def cmd_sync(
    path: str,
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
        input_path = Path(path).expanduser().resolve()

        if not input_path.exists():
            result_obj.output = LinkSyncOutput(
                path=str(input_path),
                is_monitored=False,
                links_found=0,
                links_synced=0,
                errors=["Path does not exist"],
            ).model_dump(mode="python")
            result_obj.result = f"Path not found: {path}"
            result_obj.success = False
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
        # Setup resolver once for all files
        resolver = None
        vault_root = None
        try:
            with Vault(vault_cfg) as vault:
                resolver = LinkResolver(vault.vault_path, vault.links_dir)
                vault_root = vault.vault_path
        except Exception:
            pass  # No vault configured

        yield (0.5, f"Syncing {len(files)} files...")
        total_found = 0
        total_synced = 0
        all_errors: list[str] = []

        for i, file_path in enumerate(files):
            progress = 0.5 + (0.4 * (i / len(files)))
            yield (progress, f"Syncing {file_path.name}...")

            found, synced, errors = _sync_single_file(file_path, parser, remote, config, resolver, vault_root)
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

    return StageResult(announce=f"Syncing links for {path}...", progress_callback=do_work)
