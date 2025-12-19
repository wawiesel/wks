"""Link sync API command."""

import hashlib
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from wks.api.database.Database import Database
from wks.api.vault._constants import DOC_TYPE_LINK
from wks.utils.expand_paths import expand_paths
from wks.utils.logger import get_logger
from wks.utils.uri_utils import path_to_uri, uri_to_path

from ..config.WKSConfig import WKSConfig
from ..monitor.remote_resolver import resolve_remote_uri
from ..StageResult import StageResult
from ..vault._obsidian._LinkResolver import _LinkResolver
from ..vault.Vault import Vault
from . import LinkSyncOutput

# Accessing private module as we reuse the logic
from ._parsers import get_parser

# Supported extensions for link parsing
_LINK_EXTENSIONS = {".md", ".html", ".htm", ".rst", ".txt"}


def _identity(from_uri: str, line_number: int, column_number: int, to_uri: str, remote_uri: str | None = None) -> str:
    payload = f"{from_uri}|{line_number}|{column_number}|{to_uri}|{remote_uri}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


def _sync_single_file(
    file_path: Path,
    parser_name: str | None,
    remote: bool,
    config: Any,
    resolver: Any,
    vault_root: Path | None,
) -> tuple[int, int, list[str]]:
    """Sync a single file and return (links_found, links_synced, errors).

    When explicitly called, syncs links AND registers file with monitor.
    """
    from ..monitor.cmd_sync import cmd_sync as monitor_sync

    warnings: list[str] = []

    # Auto-register file with monitor (explicit sync = intent to track)
    try:
        monitor_result = monitor_sync(str(file_path), recursive=False)
        # Execute the generator
        for _ in monitor_result.progress_callback(monitor_result):
            pass
    except Exception:
        # Non-fatal - file might be outside monitored areas but we still extract links
        warnings.append(f"Could not register with monitor: {file_path.name}")

    try:
        # Get parser
        parser_instance = get_parser(parser_name, file_path)
        actual_parser = parser_name or "auto"

        # Read file
        text = file_path.read_text(encoding="utf-8")

        # Parse links
        link_refs = parser_instance.parse(text)

        # Determine from_uri
        if vault_root and file_path.is_relative_to(vault_root):
            relative_path = file_path.relative_to(vault_root)
            from_uri = f"vault:///{relative_path}"
        else:
            from_uri = path_to_uri(file_path)

        # Determine from_remote_uri
        from_remote_uri = resolve_remote_uri(file_path, config.monitor.remote)

        # Resolve links
        records = []
        for ref in link_refs:
            to_uri = ref.raw_target

            if ref.link_type == "wikilink" and resolver:
                metadata = resolver.resolve(ref.raw_target)
                to_uri = metadata.target_uri
                if metadata.status != "ok":
                    continue  # Skip broken links

            records.append(
                {
                    "from_uri": from_uri,
                    "to_uri": to_uri,
                    "line_number": ref.line_number,
                    "column_number": ref.column_number,
                    "parser": actual_parser,
                    "name": ref.alias,
                    "status": "ok",
                    "to_remote_uri": None,
                }
            )

            # Attempt remote resolution for target
            target_path_obj = None
            try:
                if str(to_uri).startswith("vault:///"):
                    if vault_root:
                        target_path_obj = vault_root / str(to_uri)[11:]
                elif str(to_uri).startswith("file://"):
                    target_path_obj = uri_to_path(str(to_uri))
                elif "://" not in str(to_uri):
                    # Assume relative path from current file
                    try:
                        possible_path = file_path.parent / str(to_uri)
                        target_path_obj = possible_path.resolve()
                    except Exception:
                        pass

                if target_path_obj:
                    remote_uri = resolve_remote_uri(target_path_obj, config.monitor.remote)
                    if remote_uri:
                        records[-1]["to_remote_uri"] = remote_uri

            except Exception:
                pass

        # Build documents
        seen_at_iso = datetime.now(timezone.utc).isoformat()
        valid_docs = []

        for rec in records:
            if rec["status"] != "ok":
                continue

            to_uri = str(rec["to_uri"])

            # Remote validation if requested
            if remote:
                parsed = urlparse(to_uri)
                if parsed.scheme in ("http", "https"):
                    # TODO: Implement actual remote check
                    pass

            doc_id = _identity(
                str(rec["from_uri"]),
                int(str(rec["line_number"])),
                int(str(rec["column_number"])),
                str(to_uri),
                str(rec["to_remote_uri"]) if rec["to_remote_uri"] else None,
            )
            valid_docs.append(
                {
                    "_id": doc_id,
                    "doc_type": DOC_TYPE_LINK,
                    "from_local_uri": rec["from_uri"],
                    "from_remote_uri": from_remote_uri,
                    "to_local_uri": to_uri,
                    "to_remote_uri": rec["to_remote_uri"],
                    "line_number": rec["line_number"],
                    "column_number": rec["column_number"],
                    "parser": rec["parser"],
                    "name": rec["name"],
                    "last_seen": seen_at_iso,
                    "last_updated": seen_at_iso,
                }
            )

        # Write to DB
        with Database(config.database, "edges") as db:
            db.delete_many({"from_local_uri": from_uri})
            if valid_docs:
                db.insert_many(valid_docs)

        return (len(records), len(valid_docs), [])

    except Exception as e:
        logger = get_logger("link.sync")
        logger.error(f"Failed to sync file {file_path}: {e}")
        return (0, 0, [f"Error in {file_path.name}: {e}"])


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
                resolver = _LinkResolver(vault.vault_path, vault.links_dir)
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
