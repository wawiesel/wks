"""Vault link scanning and MongoDB synchronization."""

from __future__ import annotations

import hashlib
import logging
import platform
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection

from ..config.WKSConfig import WKSConfig
from .constants import (
    DOC_TYPE_LINK,
    DOC_TYPE_META,
    LINK_TYPE_EMBED,
    LINK_TYPE_MARKDOWN_URL,
    LINK_TYPE_WIKILINK,
    MAX_LINE_PREVIEW,
    META_DOCUMENT_ID,
    STATUS_OK,
)
from .link_resolver import LinkResolver
from .markdown_parser import extract_headings, parse_markdown_urls, parse_wikilinks
from .obsidian import ObsidianVault

__all__ = [
    "VaultEdgeRecord",
    "VaultLinkIndexer",
    "VaultLinkScanner",
    "VaultScanStats",
    "VaultSyncResult",
]

logger = logging.getLogger(__name__)


def _identity(note_path: str, line_number: int, target_uri: str) -> str:
    payload = f"{note_path}|{line_number}|{target_uri}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VaultEdgeRecord:
    """Single vault edge with URI-first schema.

    Uses cross-platform URIs as canonical identifiers.
    Redundant fields removed - derive on-demand from URIs and patterns.
    """

    # Source context
    note_path: str
    from_uri: str
    line_number: int
    source_heading: str
    raw_line: str

    # Link content
    link_type: str
    raw_target: str
    alias_or_text: str

    # Target resolution (URI-first)
    to_uri: str
    status: str

    @property
    def identity(self) -> str:
        return _identity(self.note_path, self.line_number, self.to_uri)

    def to_document(self, seen_at_iso: str) -> dict[str, object]:
        return {
            "_id": self.identity,
            "doc_type": DOC_TYPE_LINK,
            "from_uri": self.from_uri,
            "to_uri": self.to_uri,
            "line_number": self.line_number,
            "source_heading": self.source_heading,
            "raw_line": self.raw_line,
            "link_type": self.link_type,
            "raw_target": self.raw_target,
            "alias_or_text": self.alias_or_text,
            "status": self.status,
            "last_seen": seen_at_iso,
            "last_updated": seen_at_iso,
        }


@dataclass
class VaultScanStats:
    notes_scanned: int
    edge_total: int
    type_counts: dict[str, int]
    status_counts: dict[str, int]
    errors: list[str]
    scanned_files: set[str] = field(default_factory=set)  # Relative paths of scanned files


@dataclass
class VaultSyncResult:
    stats: VaultScanStats
    sync_started: str
    sync_duration_ms: int
    deleted_records: int
    upserts: int

    def to_meta_document(self) -> dict[str, object]:
        return {
            "_id": META_DOCUMENT_ID,
            "doc_type": DOC_TYPE_META,
            "last_scan_started_at": self.sync_started,
            "last_scan_duration_ms": self.sync_duration_ms,
            "notes_scanned": self.stats.notes_scanned,
            "edges_written": self.stats.edge_total,
            "type_counts": dict(self.stats.type_counts),
            "status_counts": dict(self.stats.status_counts),
            "errors": list(self.stats.errors),
        }


class VaultLinkScanner:
    """Parse Obsidian markdown for wiki links and URLs."""

    def __init__(self, vault: ObsidianVault):
        self.vault = vault
        self.link_resolver = LinkResolver(vault.links_dir)
        self._file_url_rewrites: list[tuple[Path, int, str, str]] = []  # (note_path, line_num, old_link, new_link)

    def scan(self, files: list[Path] | None = None) -> list[VaultEdgeRecord]:
        """Scan vault for links.

        Args:
            files: Optional list of specific files to scan. If None, scans all markdown files.

        Returns:
            List of VaultEdgeRecord objects
        """
        records: list[VaultEdgeRecord] = []
        self._errors: list[str] = []
        self._notes_scanned = 0
        self._scanned_file_paths: set[str] = set()  # Track which files were scanned
        self._type_counts: Counter[str] = Counter()
        self._status_counts: Counter[str] = Counter()
        self._file_url_rewrites = []  # Reset rewrites

        # Determine which files to scan
        files_to_scan = files if files is not None else list(self.vault.iter_markdown_files())

        for note_path in files_to_scan:
            # Skip non-markdown files if specific files provided
            if files is not None and note_path.suffix != ".md":
                continue

            self._notes_scanned += 1

            # Track relative path of scanned file
            try:
                rel_path = note_path.relative_to(self.vault.vault_path).as_posix()
                self._scanned_file_paths.add(rel_path)
            except ValueError:
                pass

            try:
                text = note_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError, PermissionError) as exc:
                self._errors.append(f"Cannot read {note_path}: {exc}")
                continue
            records.extend(self._parse_note(note_path, text))

        # Apply file:// URL rewrites (convert to wikilinks)
        self._apply_file_url_rewrites()

        self._stats = VaultScanStats(
            notes_scanned=self._notes_scanned,
            edge_total=len(records),
            type_counts=dict(self._ensure_type_keys(self._type_counts)),
            status_counts=dict(self._status_counts),
            errors=self._errors,
            scanned_files=self._scanned_file_paths,
        )
        return records

    def _apply_file_url_rewrites(self) -> None:
        """Rewrite markdown files to convert file:// URLs to [[_links/...]] wikilinks."""
        # Group rewrites by note_path
        rewrites_by_note: dict[Path, list[tuple[int, str, str]]] = {}
        for note_path, line_num, old_link, new_link in self._file_url_rewrites:
            if note_path not in rewrites_by_note:
                rewrites_by_note[note_path] = []
            rewrites_by_note[note_path].append((line_num, old_link, new_link))

        # Apply rewrites to each note
        for note_path, rewrites in rewrites_by_note.items():
            try:
                lines = note_path.read_text(encoding="utf-8").splitlines(keepends=True)

                # Apply each rewrite
                for line_num, old_link, new_link in rewrites:
                    if line_num <= len(lines):
                        lines[line_num - 1] = lines[line_num - 1].replace(old_link, new_link)

                # Write back
                note_path.write_text("".join(lines), encoding="utf-8")

            except Exception as exc:
                self._errors.append(f"Failed to rewrite {note_path}: {exc}")

    @property
    def stats(self) -> VaultScanStats:
        return self._stats

    @staticmethod
    def _ensure_type_keys(counter: Counter[str]) -> Counter[str]:
        for key in (LINK_TYPE_WIKILINK, LINK_TYPE_EMBED, LINK_TYPE_MARKDOWN_URL):
            counter.setdefault(key, 0)
        return counter

    def _parse_note(self, note_path: Path, text: str) -> list[VaultEdgeRecord]:
        """Parse all links from a markdown note.

        Args:
            note_path: Path to the note file
            text: Content of the note

        Returns:
            List of VaultEdgeRecord objects
        """
        records: list[VaultEdgeRecord] = []
        headings = extract_headings(text)
        lines = text.splitlines()

        # Parse wiki links and embeds
        for wiki_link in parse_wikilinks(text):
            record = self._build_wikilink_record(
                note_path=note_path,
                line_number=wiki_link.line_number,
                raw_line=lines[wiki_link.line_number - 1],
                heading=headings[wiki_link.line_number],
                target=wiki_link.target,
                alias=wiki_link.alias,
                is_embed=wiki_link.is_embed,
                raw_target=wiki_link.raw_target,
            )
            records.append(record)
            self._record_counts(record)

        # Parse markdown URLs
        for md_url in parse_markdown_urls(text):
            record = self._build_url_record(
                note_path=note_path,
                line_number=md_url.line_number,
                raw_line=lines[md_url.line_number - 1],
                heading=headings[md_url.line_number],
                url=md_url.url,
                alias=md_url.text,
            )
            records.append(record)
            self._record_counts(record)

        return records

    def _record_counts(self, record: VaultEdgeRecord) -> None:
        self._type_counts[record.link_type] += 1
        self._status_counts[record.status] += 1

    def _note_path(self, note_path: Path) -> str:
        return note_path.relative_to(self.vault.vault_path).as_posix()

    def _preview_line(self, line: str) -> str:
        clean = line.rstrip("\n")
        if len(clean) <= MAX_LINE_PREVIEW:
            return clean
        return f"{clean[:MAX_LINE_PREVIEW]}…"

    def _build_wikilink_record(
        self,
        note_path: Path,
        line_number: int,
        raw_line: str,
        heading: str,
        target: str,
        alias: str,
        is_embed: bool,
        raw_target: str,
    ) -> VaultEdgeRecord:
        note_rel = self._note_path(note_path)
        metadata = self.link_resolver.resolve(target)
        return VaultEdgeRecord(
            note_path=note_rel,
            from_uri=f"vault:///{note_rel}",
            line_number=line_number,
            source_heading=heading,
            raw_line=self._preview_line(raw_line),
            link_type=LINK_TYPE_EMBED if is_embed else LINK_TYPE_WIKILINK,
            raw_target=raw_target,
            alias_or_text=alias,
            to_uri=metadata.target_uri,
            status=metadata.status,
        )

    def _convert_file_url_to_symlink(self, url: str, note_path: Path, line_number: int, alias: str) -> str | None:
        """Convert file:// URL to _links/ symlink and record for rewriting.

        Only converts files, not directories. Directories stay as file:// URLs so they're clickable.

        Args:
            url: The file:// URL
            note_path: Path to the note containing the link
            line_number: Line number in the note
            alias: Link text/alias

        Returns:
            Symlink target path like "_links/<machine>/path/to/file" or None if conversion fails/skipped
        """
        if not url.startswith("file://"):
            return None

        try:
            # Parse file:// URL to get filesystem path
            parsed = urlparse(url)
            file_path = Path(parsed.path)

            if not file_path.exists():
                self._errors.append(f"File URL points to non-existent path: {url}")
                return None

            # Skip directories - keep them as file:// URLs so they're clickable in Obsidian
            if file_path.is_dir():
                logger.debug(f"Skipping directory conversion to wikilink: {url}")
                return None

            # Get machine name
            machine = platform.node().split(".")[0]  # e.g., "lap139160"

            # Create symlink path: _links/<machine>/path/to/file
            # Strip leading / from path
            rel_path = str(file_path).lstrip("/")
            symlink_target = f"_links/{machine}/{rel_path}"
            symlink_path = self.vault.links_dir / machine / rel_path

            # Create symlink if it doesn't exist
            if not symlink_path.exists():
                symlink_path.parent.mkdir(parents=True, exist_ok=True)
                symlink_path.symlink_to(file_path)

            # Record markdown rewrite needed
            old_markdown = f"[{alias}]({url})"
            new_markdown = f"[[{symlink_target}]]"
            self._file_url_rewrites.append((note_path, line_number, old_markdown, new_markdown))

            return symlink_target

        except Exception as exc:
            self._errors.append(f"Failed to convert file URL {url}: {exc}")
            return None

    def _build_url_record(
        self,
        note_path: Path,
        line_number: int,
        raw_line: str,
        heading: str,
        url: str,
        alias: str,
    ) -> VaultEdgeRecord:
        note_rel = self._note_path(note_path)

        # Handle file:// URLs specially - convert to symlink
        if url.startswith("file://"):
            symlink_target = self._convert_file_url_to_symlink(url, note_path, line_number, alias)
            if symlink_target:
                # Return a wikilink record pointing to the symlink
                metadata = self.link_resolver.resolve(symlink_target)
                return VaultEdgeRecord(
                    note_path=note_rel,
                    from_uri=f"vault:///{note_rel}",
                    line_number=line_number,
                    source_heading=heading,
                    raw_line=self._preview_line(raw_line),
                    link_type=LINK_TYPE_WIKILINK,  # Convert to wikilink type
                    raw_target=symlink_target,
                    alias_or_text=alias,
                    to_uri=metadata.target_uri,
                    status=metadata.status,
                )

        # Regular external URL (https://)
        return VaultEdgeRecord(
            note_path=note_rel,
            from_uri=f"vault:///{note_rel}",
            line_number=line_number,
            source_heading=heading,
            raw_line=self._preview_line(raw_line),
            link_type=LINK_TYPE_MARKDOWN_URL,
            raw_target=url,
            alias_or_text=alias,
            to_uri=url,
            status=STATUS_OK,
        )


class VaultLinkIndexer:
    """Coordinates scanning and MongoDB writes."""

    def __init__(
        self,
        vault: ObsidianVault,
        *,
        mongo_uri: str,
        db_name: str,
        coll_name: str,
    ):
        self.vault = vault
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.coll_name = coll_name

    @contextmanager
    def _mongo_connection(self) -> Iterator[Collection]:
        """Context manager for MongoDB connections with automatic cleanup.

        Yields:
            MongoDB collection object

        Ensures client is closed even if exceptions occur.
        """
        client: MongoClient = MongoClient(
            self.mongo_uri,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            retryReads=True,
        )
        try:
            yield client[self.db_name][self.coll_name]
        finally:
            client.close()

    @classmethod
    def from_config(cls, vault: ObsidianVault, cfg: Any | None = None) -> VaultLinkIndexer:
        if cfg is None:
            config = WKSConfig.load()
        elif isinstance(cfg, dict):
            # Backward compatibility for dict config
            # We should ideally convert dict to WKSConfig here or just handle it manually
            # For now, let's try to load WKSConfig if possible, or extract from dict
            try:
                config = WKSConfig.load()
            except Exception:
                # Fallback manual extraction from dict
                mongo_uri = cfg.get("database", {}).get("data", {}).get("uri") or cfg.get("db", {}).get("uri")
                db_key = cfg.get("vault", {}).get("database")
                db_name, coll_name = db_key.split(".", 1)
                return cls(vault=vault, mongo_uri=mongo_uri, db_name=db_name, coll_name=coll_name)
        else:
            config = cfg

        mongo_uri = config.database.get_uri()
        db_name = config.vault.database.split(".")[0]
        coll_name = config.vault.database.split(".")[1]

        return cls(vault=vault, mongo_uri=mongo_uri, db_name=db_name, coll_name=coll_name)

    def _batch_records(self, records: list[VaultEdgeRecord], batch_size: int) -> Iterator[list[VaultEdgeRecord]]:
        """Yield successive batches of records."""
        for i in range(0, len(records), batch_size):
            yield records[i : i + batch_size]

    def has_references_to(self, file_path: Path) -> bool:
        """Check if any vault notes reference this file.

        Args:
            file_path: Path to check for references

        Returns:
            True if vault has links pointing to this file
        """
        try:
            # Convert path to the _links/ format used in vault
            rel_path = self.vault._link_rel_for_source(file_path)
            vault_uri = f"vault:///{rel_path}"

            with self._mongo_connection() as coll:
                # Check if any links point TO this file
                count = coll.count_documents({"to_uri": vault_uri}, limit=1)
                return count > 0
        except Exception:
            return False

    def update_links_on_file_move(self, old_uri: str, new_uri: str) -> int:
        """Update vault DB when a file moves.

        Updates both from_uri and to_uri fields where they reference the moved file.

        Args:
            old_uri: Old file:// or vault:/// URI
            new_uri: New file:// or vault:/// URI

        Returns:
            Number of links updated
        """
        with self._mongo_connection() as collection:
            # Update links TO the moved file
            result_to = collection.update_many(
                {"to_uri": old_uri},
                {
                    "$set": {
                        "to_uri": new_uri,
                        "status": STATUS_OK,  # Clear any missing_target status
                        "last_updated": _now_iso(),
                    }
                },
            )

            # Update links FROM the moved file
            result_from = collection.update_many(
                {"from_uri": old_uri},
                {
                    "$set": {
                        "from_uri": new_uri,
                        "last_updated": _now_iso(),
                    }
                },
            )

            return result_to.modified_count + result_from.modified_count

    def sync(self, batch_size: int = 1000, incremental: bool = False) -> VaultSyncResult:
        """Sync vault links to MongoDB with batch processing.

        Args:
            batch_size: Number of records to process per batch (default 1000).
                       Larger batches are faster but use more memory.
                       Smaller batches are safer for very large vaults.
            incremental: If True, use git to detect changed files and only scan those.
                        If False, scan all files (default).

        Returns:
            VaultSyncResult with sync statistics
        """
        scanner = VaultLinkScanner(self.vault)

        # Determine which files to scan
        files_to_scan = None
        if incremental:
            try:
                from .git_watcher import GitVaultWatcher

                watcher = GitVaultWatcher(self.vault.vault_path)
                changes = watcher.get_changes()

                if changes.has_changes:
                    files_to_scan = list(changes.all_affected_files)
                    logger.info(f"Git incremental scan: {len(files_to_scan)} changed files")
                else:
                    # No changes detected, return empty result
                    logger.debug("No git changes detected, skipping scan")
                    return VaultSyncResult(
                        stats=VaultScanStats(
                            notes_scanned=0,
                            edge_total=0,
                            type_counts={},
                            status_counts={},
                            errors=[],
                        ),
                        sync_started=_now_iso(),
                        sync_duration_ms=0,
                        deleted_records=0,
                        upserts=0,
                    )
            except Exception as exc:
                logger.warning(f"Git incremental scan failed, falling back to full scan: {exc}")
                incremental = False

        records = scanner.scan(files=files_to_scan)
        stats = scanner.stats
        started = time.perf_counter()
        started_iso = _now_iso()

        with self._mongo_connection() as collection:
            total_upserts = 0

            # Process records in batches to avoid memory issues
            for batch in self._batch_records(records, batch_size):
                ops: list[UpdateOne] = []
                for record in batch:
                    doc = record.to_document(seen_at_iso=started_iso)
                    ops.append(
                        UpdateOne(
                            {"_id": record.identity},
                            {
                                "$set": doc,
                                "$setOnInsert": {"first_seen": started_iso},
                            },
                            upsert=True,
                        )
                    )

                if ops:
                    result = collection.bulk_write(ops, ordered=False)
                    total_upserts += result.upserted_count + result.modified_count

            # Only delete stale links from files that were actually scanned in this run
            # This prevents incremental scans from wiping out links from non-scanned files
            delete_query = {
                "doc_type": DOC_TYPE_LINK,
                "last_seen": {"$lt": started_iso},
                "from": {"$in": list(stats.scanned_files)} if stats.scanned_files else [],
            }
            deleted = collection.delete_many(delete_query).deleted_count

            result_summary = VaultSyncResult(
                stats=stats,
                sync_started=started_iso,
                sync_duration_ms=int((time.perf_counter() - started) * 1000),
                deleted_records=deleted,
                upserts=total_upserts,
            )
            collection.replace_one({"_id": META_DOCUMENT_ID}, result_summary.to_meta_document(), upsert=True)

        return result_summary
