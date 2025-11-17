"""Vault link scanning and MongoDB synchronization."""

from __future__ import annotations

import hashlib
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pymongo import MongoClient, UpdateOne

from ..db_helpers import parse_database_key
from ..config import load_config
from .obsidian import ObsidianVault

WIKILINK_PATTERN = re.compile(r"(!)?\[\[([^\]]+)\]\]")
MARKDOWN_URL_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_MAX_LINE_PREVIEW = 400


def _identity(note_path: str, line_number: int, target_uri: str) -> str:
    payload = f"{note_path}|{line_number}|{target_uri}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VaultEdgeRecord:
    """Single vault edge flattened into the canonical schema."""

    note_path: str
    line_number: int
    source_heading: str
    raw_line: str
    link_type: str
    raw_target: str
    alias_or_text: str
    is_embed: bool
    target_kind: str
    target_uri: str
    links_rel: str
    resolved_path: str
    resolved_exists: bool
    status: str
    monitor_doc_id: str = ""

    @property
    def identity(self) -> str:
        return _identity(self.note_path, self.line_number, self.target_uri)

    def to_document(self, seen_at_iso: str) -> Dict[str, object]:
        return {
            "_id": self.identity,
            "doc_type": "link",
            "note_path": self.note_path,
            "line_number": self.line_number,
            "source_heading": self.source_heading,
            "raw_line": self.raw_line,
            "link_type": self.link_type,
            "raw_target": self.raw_target,
            "alias_or_text": self.alias_or_text,
            "is_embed": self.is_embed,
            "target_kind": self.target_kind,
            "target_uri": self.target_uri,
            "links_rel": self.links_rel,
            "resolved_path": self.resolved_path,
            "resolved_exists": self.resolved_exists,
            "monitor_doc_id": self.monitor_doc_id,
            "status": self.status,
            "last_seen": seen_at_iso,
            "last_updated": seen_at_iso,
        }


@dataclass
class VaultScanStats:
    notes_scanned: int
    edge_total: int
    type_counts: Dict[str, int]
    status_counts: Dict[str, int]
    errors: List[str]


@dataclass
class VaultSyncResult:
    stats: VaultScanStats
    sync_started: str
    sync_duration_ms: int
    deleted_records: int
    upserts: int

    def to_meta_document(self) -> Dict[str, object]:
        return {
            "_id": "__meta__",
            "doc_type": "meta",
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

    def scan(self) -> List[VaultEdgeRecord]:
        records: List[VaultEdgeRecord] = []
        self._errors: List[str] = []
        self._notes_scanned = 0
        self._type_counts: Counter[str] = Counter()
        self._status_counts: Counter[str] = Counter()

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
            edge_total=len(records),
            type_counts=dict(self._ensure_type_keys(self._type_counts)),
            status_counts=dict(self._status_counts),
            errors=self._errors,
        )
        return records

    @property
    def stats(self) -> VaultScanStats:
        return self._stats

    @staticmethod
    def _ensure_type_keys(counter: Counter[str]) -> Counter[str]:
        for key in ("wikilink", "embed", "markdown_url"):
            counter.setdefault(key, 0)
        return counter

    def _parse_note(self, note_path: Path, text: str) -> List[VaultEdgeRecord]:
        rows: List[VaultEdgeRecord] = []
        lines = text.splitlines()
        heading = ""
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
            for match in WIKILINK_PATTERN.finditer(line):
                is_embed = bool(match.group(1))
                raw_target = match.group(2).strip()
                target, alias = self._split_alias(raw_target)
                record = self._build_wikilink_record(
                    note_path=note_path,
                    line_number=idx,
                    raw_line=line,
                    heading=heading,
                    target=target,
                    alias=alias,
                    is_embed=is_embed,
                    raw_target=raw_target,
                )
                rows.append(record)
                self._record_counts(record)
            for match in MARKDOWN_URL_PATTERN.finditer(line):
                url = match.group(2).strip()
                alias = match.group(1).strip()
                record = self._build_url_record(
                    note_path=note_path,
                    line_number=idx,
                    raw_line=line,
                    heading=heading,
                    url=url,
                    alias=alias,
                )
                rows.append(record)
                self._record_counts(record)
        return rows

    def _record_counts(self, record: VaultEdgeRecord) -> None:
        self._type_counts[record.link_type] += 1
        self._status_counts[record.status] += 1

    @staticmethod
    def _split_alias(target: str) -> tuple[str, str]:
        if "|" in target:
            core, alias = target.split("|", 1)
            return core.strip(), alias.strip()
        return target.strip(), ""

    def _note_path(self, note_path: Path) -> str:
        return note_path.relative_to(self.vault.vault_path).as_posix()

    def _preview_line(self, line: str) -> str:
        clean = line.rstrip("\n")
        if len(clean) <= _MAX_LINE_PREVIEW:
            return clean
        return f"{clean[:_MAX_LINE_PREVIEW]}…"

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
        metadata = self._resolve_wikilink_target(target)
        return VaultEdgeRecord(
            note_path=note_rel,
            line_number=line_number,
            source_heading=heading,
            raw_line=self._preview_line(raw_line),
            link_type="embed" if is_embed else "wikilink",
            raw_target=raw_target,
            alias_or_text=alias,
            is_embed=is_embed,
            target_kind=metadata["target_kind"],
            target_uri=metadata["target_uri"],
            links_rel=metadata["links_rel"],
            resolved_path=metadata["resolved_path"],
            resolved_exists=metadata["resolved_exists"],
            status=metadata["status"],
        )

    def _resolve_wikilink_target(self, target: str) -> Dict[str, object]:
        target = target.strip()
        lowered = target.lower()
        data: Dict[str, object] = {
            "target_kind": "vault_note",
            "target_uri": f"vault:///{target}",
            "links_rel": "",
            "resolved_path": "",
            "resolved_exists": False,
            "status": "ok",
        }
        if lowered.startswith("links/"):
            normalized = target[target.lower().index("links/") + len("links/") :]
            data["target_kind"] = "legacy_path"
            data["target_uri"] = f"legacy:///{normalized}"
            data["status"] = "legacy_link"
            return data
        if target.startswith("_links/"):
            rel = target[len("_links/") :]
            symlink_path = self.vault.links_dir / rel
            data["target_kind"] = "_links_symlink"
            data["target_uri"] = f"vault-link:///{target}"
            data["links_rel"] = target
            data["resolved_path"] = str(symlink_path)
            if not symlink_path.exists():
                data["status"] = "missing_symlink"
            else:
                try:
                    resolved = symlink_path.resolve(strict=False)
                except Exception:
                    resolved = symlink_path
                data["resolved_path"] = str(resolved)
                data["resolved_exists"] = resolved.exists()
                if not data["resolved_exists"]:
                    data["status"] = "missing_target"
            return data
        if target.startswith("_"):
            data["target_kind"] = "attachment"
            data["target_uri"] = f"vault:///{target}"
            return data
        if "://" in target:
            data["target_kind"] = "external_url"
            data["target_uri"] = target
            return data
        if target.startswith("/"):
            data["target_kind"] = "legacy_path"
            data["target_uri"] = f"legacy:///{target}"
            data["status"] = "legacy_link"
            return data
        return data

    def _build_url_record(
        self,
        note_path: Path,
        line_number: int,
        raw_line: str,
        heading: str,
        url: str,
        alias: str,
    ) -> VaultEdgeRecord:
        return VaultEdgeRecord(
            note_path=self._note_path(note_path),
            line_number=line_number,
            source_heading=heading,
            raw_line=self._preview_line(raw_line),
            link_type="markdown_url",
            raw_target=url,
            alias_or_text=alias,
            is_embed=False,
            target_kind="external_url",
            target_uri=url,
            links_rel="",
            resolved_path="",
            resolved_exists=False,
            status="ok",
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
