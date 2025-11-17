"""Vault link scanning and MongoDB synchronization."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from pymongo import MongoClient, UpdateOne

from ..db_helpers import parse_database_key
from ..config import load_config
from ..constants import WKS_HOME_DISPLAY
from .obsidian import ObsidianVault

WIKILINK_PATTERN = re.compile(r"(!)?\[\[([^\]]+)\]\]")
MARKDOWN_URL_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _identity(from_note: str, line_number: int, target: str) -> str:
    payload = f"{from_note}|{line_number}|{target}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VaultLinkRecord:
    """Single link parsed from the vault."""

    identity: str
    from_note: str
    note_path: str
    line_number: int
    link_type: str
    link_target_uri: str
    link_status: str
    embed_link: Optional[str]
    resolved_path: Optional[str]
    alias: Optional[str]
    raw_target: str

    def to_document(self, seen_at_iso: str) -> Dict[str, object]:
        doc = {
            "_id": self.identity,
            "doc_type": "link",
            "from_note": self.from_note,
            "note_path": self.note_path,
            "line_number": self.line_number,
            "link_type": self.link_type,
            "link_target_uri": self.link_target_uri,
            "link_status": self.link_status,
            "embed_link": self.embed_link,
            "resolved_path": self.resolved_path,
            "alias": self.alias,
            "raw_target": self.raw_target,
            "last_seen": seen_at_iso,
        }
        return doc


@dataclass
class VaultScanStats:
    notes_scanned: int
    link_records: int
    wiki_links: int
    embeds: int
    markdown_urls: int
    errors: List[str]


@dataclass
class VaultSyncResult:
    stats: VaultScanStats
    sync_started: str
    sync_duration_ms: int
    deleted_records: int
    upserts: int

    def to_meta_document(self) -> Dict[str, object]:
        meta = {
            "_id": "__meta__",
            "doc_type": "meta",
            "last_scan_started_at": self.sync_started,
            "last_scan_duration_ms": self.sync_duration_ms,
            "notes_scanned": self.stats.notes_scanned,
            "records_written": self.stats.link_records,
            "wiki_links": self.stats.wiki_links,
            "embeds": self.stats.embeds,
            "markdown_urls": self.stats.markdown_urls,
            "errors": list(self.stats.errors),
        }
        return meta


class VaultLinkScanner:
    """Parse Obsidian markdown for wiki links and URLs."""

    def __init__(self, vault: ObsidianVault):
        self.vault = vault

    def scan(self) -> List[VaultLinkRecord]:
        records: List[VaultLinkRecord] = []
        self._errors: List[str] = []
        self._notes_scanned = 0
        self._wiki_links = 0
        self._embeds = 0
        self._urls = 0

        for note_path in self.vault.iter_markdown_files():
            self._notes_scanned += 1
            try:
                text = note_path.read_text(encoding="utf-8")
            except Exception as exc:  # pragma: no cover - rare I/O issues
                self._errors.append(f"{note_path}: {exc}")
                continue
            records.extend(self._parse_note(note_path, text))

        self._stats = VaultScanStats(
            notes_scanned=self._notes_scanned,
            link_records=len(records),
            wiki_links=self._wiki_links,
            embeds=self._embeds,
            markdown_urls=self._urls,
            errors=self._errors,
        )
        return records

    @property
    def stats(self) -> VaultScanStats:
        return self._stats

    def _parse_note(self, note_path: Path, text: str) -> List[VaultLinkRecord]:
        rows = []
        lines = text.splitlines()
        for idx, line in enumerate(lines, start=1):
            for match in WIKILINK_PATTERN.finditer(line):
                is_embed = bool(match.group(1))
                raw_target = match.group(2).strip()
                target, alias = self._split_alias(raw_target)
                record = self._build_wikilink_record(
                    note_path,
                    idx,
                    target,
                    alias,
                    is_embed,
                    raw_target,
                )
                rows.append(record)
                if is_embed:
                    self._embeds += 1
                else:
                    self._wiki_links += 1
            for match in MARKDOWN_URL_PATTERN.finditer(line):
                url = match.group(2).strip()
                alias = match.group(1).strip() or None
                record = self._build_url_record(note_path, idx, url, alias)
                rows.append(record)
                self._urls += 1
        return rows

    @staticmethod
    def _split_alias(target: str) -> tuple[str, Optional[str]]:
        if "|" in target:
            core, alias = target.split("|", 1)
            return core.strip(), alias.strip() or None
        return target.strip(), None

    def _note_uris(self, note_path: Path) -> tuple[str, str]:
        rel = note_path.relative_to(self.vault.vault_path)
        return f"vault:///{rel.as_posix()}", rel.as_posix()

    def _build_wikilink_record(
        self,
        note_path: Path,
        line_number: int,
        target: str,
        alias: Optional[str],
        is_embed: bool,
        raw_target: str,
    ) -> VaultLinkRecord:
        from_note, rel_note = self._note_uris(note_path)
        identity = _identity(from_note, line_number, target)
        link_type = "embed" if is_embed else "wikilink"
        link_status = "ok"
        embed_link = None
        resolved_path = None
        link_target_uri = target

        if target.lower().startswith("links/"):
            link_status = "legacy_link"
            normalized = target[target.lower().index("links/") + len("links/") :]
            link_target_uri = f"vault-link:///_links/{normalized}"
            embed_link = f"_links/{normalized}"
        elif target.startswith("_links/"):
            link_target_uri = f"vault-link:///{target}"
            embed_link = target
        elif target.startswith("_"):
            # Respect other vault-internal directories like _attachments
            link_target_uri = f"vault:///{target}"
        elif "://" not in target and not target.startswith("/"):
            link_target_uri = f"vault:///{target}"

        if embed_link:
            rel = embed_link[len("_links/") :] if embed_link.startswith("_links/") else embed_link
            symlink_path = self.vault.links_dir / rel
            if not symlink_path.exists():
                link_status = "missing_symlink"
            else:
                try:
                    resolved = symlink_path.resolve(strict=False)
                except Exception:
                    resolved = symlink_path
                resolved_path = str(resolved)
                if not resolved.exists():
                    link_status = "missing_target"

        return VaultLinkRecord(
            identity=identity,
            from_note=from_note,
            note_path=rel_note,
            line_number=line_number,
            link_type=link_type,
            link_target_uri=link_target_uri,
            link_status=link_status,
            embed_link=embed_link,
            resolved_path=resolved_path,
            alias=alias,
            raw_target=raw_target,
        )

    def _build_url_record(
        self,
        note_path: Path,
        line_number: int,
        url: str,
        alias: Optional[str],
    ) -> VaultLinkRecord:
        from_note, rel_note = self._note_uris(note_path)
        identity = _identity(from_note, line_number, url)
        return VaultLinkRecord(
            identity=identity,
            from_note=from_note,
            note_path=rel_note,
            line_number=line_number,
            link_type="markdown_url",
            link_target_uri=url,
            link_status="ok",
            embed_link=None,
            resolved_path=None,
            alias=alias,
            raw_target=url,
        )


class VaultLinkIndexer:
    """Coordinates scanning and MongoDB writes."""

    def __init__(
        self,
        vault: ObsidianVault,
        *,
        mongo_uri: str,
        collection_key: str,
    ):
        if not mongo_uri:
            raise ValueError("db.uri is required to sync vault links")
        if not collection_key:
            raise ValueError("vault.database is required to sync vault links")
        db_name, coll_name = parse_database_key(collection_key)
        self.vault = vault
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.coll_name = coll_name

    @classmethod
    def from_config(cls, vault: ObsidianVault, cfg: Optional[Dict[str, object]] = None) -> "VaultLinkIndexer":
        config = cfg or load_config()
        db_cfg = config.get("db")
        if not db_cfg or not db_cfg.get("uri"):
            raise KeyError("db.uri is required in config (found: missing, expected: MongoDB connection URI string)")
        vault_cfg = config.get("vault")
        if not vault_cfg or not vault_cfg.get("database"):
            raise KeyError("vault.database is required in config (found: missing, expected: 'database.collection' value)")
        return cls(
            vault=vault,
            mongo_uri=db_cfg["uri"],
            collection_key=vault_cfg["database"],
        )

    def sync(self) -> VaultSyncResult:
        scanner = VaultLinkScanner(self.vault)
        records = scanner.scan()
        stats = scanner.stats
        started = time.perf_counter()
        started_iso = _now_iso()

        client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
        collection = client[self.db_name][self.coll_name]

        ops: List[UpdateOne] = []
        for record in records:
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

        upserts = 0
        if ops:
            result = collection.bulk_write(ops, ordered=False)
            upserts = result.upserted_count + result.modified_count

        deleted = collection.delete_many(
            {"doc_type": "link", "last_seen": {"$lt": started_iso}}
        ).deleted_count

        result_summary = VaultSyncResult(
            stats=stats,
            sync_started=started_iso,
            sync_duration_ms=int((time.perf_counter() - started) * 1000),
            deleted_records=deleted,
            upserts=upserts,
        )
        collection.replace_one({"_id": "__meta__"}, result_summary.to_meta_document(), upsert=True)
        client.close()

        return result_summary
