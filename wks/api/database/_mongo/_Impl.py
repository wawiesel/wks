"""MongoDB collection implementation."""

import subprocess
import time
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.uri_parser import parse_uri

from .._AbstractImpl import _AbstractImpl
from ..DatabaseConfig import DatabaseConfig
from ._Data import _Data as _DatabaseConfigData


class _Impl(_AbstractImpl):
    def __init__(self, database_config: DatabaseConfig, database_name: str, collection_name: str):
        """Initialize MongoDB implementation.

        Note: Internally MongoDB uses "collections" but the public API uses "database" terminology.
        The collection_name parameter maps to a MongoDB collection.
        """
        if not isinstance(database_config.data, _DatabaseConfigData):
            raise ValueError("MongoDB config data is required")
        self.local = database_config.data.local
        self.uri = database_config.data.uri
        self.database_name = database_name
        self.collection_name = collection_name  # MongoDB collection name
        self._client: MongoClient | None = None
        self._collection: Collection | None = None
        self._mongod_proc: subprocess.Popen | None = None
        self._started_local: bool = False

    def __enter__(self):
        uri = self.uri
        if self.local:
            self._ensure_local_mongod(uri)
        self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._client.server_info()  # Test connection
        self._collection = self._client[self.database_name][self.collection_name]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()
        if self._started_local and self._mongod_proc:
            try:
                self._mongod_proc.terminate()
                self._mongod_proc.wait(timeout=5)
            except Exception:
                pass
        return False

    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        return self._collection.count_documents(filter or {})  # type: ignore[union-attr]

    def find_one(self, filter: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._collection.find_one(filter, projection)  # type: ignore[union-attr]

    def update_one(self, filter: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> None:
        self._collection.update_one(filter, update, upsert=upsert)  # type: ignore[union-attr]

    def update_many(self, filter: dict[str, Any], update: dict[str, Any]) -> int:
        result = self._collection.update_many(filter, update)  # type: ignore[union-attr]
        return result.modified_count

    def delete_many(self, filter: dict[str, Any]) -> int:
        return self._collection.delete_many(filter).deleted_count  # type: ignore[union-attr]

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> Any:
        return self._collection.find(filter or {}, projection)  # type: ignore[union-attr]

    def list_collection_names(self) -> list[str]:
        return self._client[self.database_name].list_collection_names()  # type: ignore[union-attr]

    # Internal helpers
    def _ensure_local_mongod(self, uri: str) -> None:
        """Start local mongod if not reachable."""
        if self._can_connect(uri):
            return
        host, port = self._parse_host_port(uri)
        db_path = self._default_db_path()
        db_path.mkdir(parents=True, exist_ok=True)
        cmd = [
            "mongod",
            f"--dbpath={db_path}",
            f"--bind_ip={host}",
            f"--port={port}",
            "--quiet",
        ]
        try:
            self._mongod_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._started_local = True
        except FileNotFoundError as exc:
            raise RuntimeError("mongod binary not found; install MongoDB or specify database.uri") from exc
        # Wait briefly for mongod to come up
        for _ in range(10):
            if self._can_connect(uri):
                return
            time.sleep(0.1)
        raise RuntimeError("Failed to start local mongod (timeout)")

    def _can_connect(self, uri: str) -> bool:
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=500)
            client.server_info()
            client.close()
            return True
        except Exception:
            return False

    @staticmethod
    def _default_db_path() -> Path:
        from ...config.WKSConfig import WKSConfig

        return WKSConfig.get_home_dir() / "mongo-data"

    @staticmethod
    def _parse_host_port(uri: str) -> tuple[str, int]:
        parsed = parse_uri(uri)
        if not parsed.get("nodelist"):
            raise RuntimeError("database.uri must include host:port when local=true")
        host, port = parsed["nodelist"][0]
        if port is None:
            port = 27017
        return host, port
