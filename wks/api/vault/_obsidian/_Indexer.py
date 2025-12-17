"""Vault link indexer (private)."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection

from ...config.WKSConfig import WKSConfig
from .._AbstractVault import _AbstractVault
from .._constants import DOC_TYPE_LINK, META_DOCUMENT_ID, STATUS_OK
from ._Data import _EdgeRecord, _ScanStats, _SyncResult
from ._Scanner import _Scanner

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Indexer:
    """Coordinates scanning and MongoDB writes."""

    def __init__(
        self,
        vault: _AbstractVault,
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
        """Context manager for MongoDB connections with automatic cleanup."""
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
    def from_config(cls, vault: _AbstractVault, cfg: Any | None = None) -> _Indexer:
        if cfg is None:
            config = WKSConfig.load()
        elif isinstance(cfg, dict):
            try:
                config = WKSConfig.load()
            except Exception:
                mongo_uri = cfg.get("database", {}).get("data", {}).get("uri") or cfg.get("db", {}).get("uri")
                db_key = cfg.get("vault", {}).get("database")
                db_name, coll_name = db_key.split(".", 1)
                return cls(vault=vault, mongo_uri=mongo_uri, db_name=db_name, coll_name=coll_name)
        else:
            config = cfg

        from ...database._mongo._DbConfigData import _DbConfigData as _MongoDbConfigData

        config_any: Any = config
        if isinstance(config_any.database.data, _MongoDbConfigData):
            mongo_uri = config_any.database.data.uri
        else:
            raise ValueError(f"Vault requires mongo backend, got {config_any.database.type}")
        db_name = config_any.vault.database.split(".")[0]
        coll_name = config_any.vault.database.split(".")[1]

        return cls(vault=vault, mongo_uri=mongo_uri, db_name=db_name, coll_name=coll_name)

    def _batch_records(self, records: list[_EdgeRecord], batch_size: int) -> Iterator[list[_EdgeRecord]]:
        """Yield successive batches of records."""
        for i in range(0, len(records), batch_size):
            yield records[i : i + batch_size]

    def has_references_to(self, file_path: Path) -> bool:
        """Check if any vault notes reference this file."""
        try:
            rel_path = self.vault._link_rel_for_source(file_path)
            vault_uri = f"vault:///{rel_path}"

            with self._mongo_connection() as coll:
                count = coll.count_documents({"to_uri": vault_uri}, limit=1)
                return count > 0
        except Exception:
            return False

    def update_links_on_file_move(self, old_uri: str, new_uri: str) -> int:
        """Update vault DB when a file moves."""
        with self._mongo_connection() as collection:
            result_to = collection.update_many(
                {"to_uri": old_uri},
                {
                    "$set": {
                        "to_uri": new_uri,
                        "status": STATUS_OK,
                        "last_updated": _now_iso(),
                    }
                },
            )

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

    def sync(self, batch_size: int = 1000, incremental: bool = False) -> _SyncResult:
        """Sync vault links to MongoDB with batch processing."""
        scanner = _Scanner(self.vault)

        files_to_scan = None
        if incremental:
            try:
                from ._GitWatcher import _GitWatcher

                watcher = _GitWatcher(self.vault.vault_path)
                changes = watcher.get_changes()

                if changes.has_changes:
                    files_to_scan = list(changes.all_affected_files)
                    logger.info(f"Git incremental scan: {len(files_to_scan)} changed files")
                else:
                    logger.debug("No git changes detected, skipping scan")
                    return _SyncResult(
                        stats=_ScanStats(
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

            delete_query = {
                "doc_type": DOC_TYPE_LINK,
                "last_seen": {"$lt": started_iso},
                "from": {"$in": list(stats.scanned_files)} if stats.scanned_files else [],
            }
            deleted = collection.delete_many(delete_query).deleted_count

            result_summary = _SyncResult(
                stats=stats,
                sync_started=started_iso,
                sync_duration_ms=int((time.perf_counter() - started) * 1000),
                deleted_records=deleted,
                upserts=total_upserts,
            )
            collection.replace_one({"_id": META_DOCUMENT_ID}, result_summary.to_meta_document(), upsert=True)

        return result_summary
