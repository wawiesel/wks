from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.log.append_log import append_log
from wks.api.vault._constants import DOC_TYPE_LINK

from ..monitor.resolve_remote_uri import resolve_remote_uri
from ..URI import URI
from ._identity import _identity
from ._parsers import get_parser


def _sync_single_file(
    file_path: Path,
    parser_name: str | None,
    remote: bool,
    config: Any,
    resolver_func: Any,
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
            from_uri = str(URI.from_path(file_path))

        # Determine from_remote_uri
        from_remote_uri = resolve_remote_uri(file_path, config.monitor.remote)

        # Resolve links
        records = []
        for ref in link_refs:
            to_uri = ref.raw_target

            if ref.link_type == "wikilink" and resolver_func:
                metadata = resolver_func(ref.raw_target)
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
                    target_path_obj = URI(str(to_uri)).path
                elif "://" not in str(to_uri):
                    # Assume relative path from current file
                    try:
                        from wks.utils.normalize_path import normalize_path

                        possible_path = file_path.parent / str(to_uri)
                        target_path_obj = normalize_path(possible_path)
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
                    pass  # Remote URL validation not yet implemented

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
        from contextlib import suppress

        with suppress(Exception):
            append_log(WKSConfig.get_logfile_path(), "link.sync", "ERROR", f"Failed to sync file {file_path}: {e}")
        return (0, 0, [f"Error in {file_path.name}: {e}"])
