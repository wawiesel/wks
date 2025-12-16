"""MongoDB collection implementation."""

import subprocess
import time
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.uri_parser import parse_uri

from ...config.WKSConfig import WKSConfig
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

        # Determine paths and defaults
        self.db_path = WKSConfig.get_home_dir() / "database" / "mongo"

        self.database_name = database_name
        self.collection_name = collection_name  # MongoDB collection name
        self._client: MongoClient[Any] | None = None
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
        if self._client is None:
            raise RuntimeError("Mongo client not initialized")
        return self._client[self.database_name].list_collection_names()

    # Internal helpers
    def _ensure_local_mongod(self, uri: str) -> None:
        """Start local mongod if not reachable."""
        if self._can_connect(uri):
            return
        host, port = self._parse_host_port(uri)

        # Use hardcoded db_path based on WKS_HOME
        db_path = self.db_path
        db_path.mkdir(parents=True, exist_ok=True)
        # Resolve mongod binary path
        import shutil
        mongod_bin = shutil.which("mongod")
        if not mongod_bin:
            # Try common fallback paths
            for fallback in ["/opt/homebrew/bin/mongod", "/usr/local/bin/mongod", "/usr/bin/mongod"]:
                if Path(fallback).exists():
                    mongod_bin = fallback
                    break
        
        if not mongod_bin:
             raise RuntimeError("mongod binary not found; install MongoDB or specify database.uri")

        cmd = [
            mongod_bin,
            f"--dbpath={db_path}",
            f"--bind_ip={host}",
            f"--port={port}",
            "--quiet",
        ]
        try:
            # Capture stderr to diagnose startup issues
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as stderr_file:
                stderr_path = Path(stderr_file.name)
                self._mongod_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                )
                self._started_local = True
        except FileNotFoundError as exc:
            raise RuntimeError("mongod binary not found; install MongoDB or specify database.uri") from exc
        # Wait for mongod to come up (increased timeout for CI - mongod can take 5-10 seconds to start)
        max_attempts = 50  # 50 * 0.2s = 10 seconds total
        for _attempt in range(max_attempts):
            # Check if process crashed early
            if self._mongod_proc.poll() is not None:
                error_output = stderr_path.read_text() if stderr_path.exists() else ""
                stderr_path.unlink(missing_ok=True)
                # Exit code 48 means "Address already in use" - port conflict
                if self._mongod_proc.returncode == 48:
                    raise RuntimeError(
                        f"mongod port {port} is already in use (likely from parallel test execution). "
                        f"Try using a different port or ensure previous mongod processes are cleaned up."
                    )
                # Exit code 100 means data directory issue (lock, corruption, or incompatible version)
                if self._mongod_proc.returncode == 100:
                    raise RuntimeError(
                        f"mongod data directory issue at {db_path} (exit code 100). "
                        f"This usually means the directory is locked by another mongod process or corrupted. "
                        f"Error output: {error_output[:500]}"
                    )
                raise RuntimeError(
                    f"mongod process exited with code {self._mongod_proc.returncode}. "
                    f"Error output: {error_output[:500]}"
                )
            if self._can_connect(uri):
                stderr_path.unlink(missing_ok=True)
                return
            time.sleep(0.2)  # Increased sleep interval for better responsiveness

        # Check if process is still running (might have crashed)
        if self._mongod_proc and self._mongod_proc.poll() is not None:
            error_output = stderr_path.read_text() if stderr_path.exists() else ""
            stderr_path.unlink(missing_ok=True)
            # Exit code 48 means "Address already in use" - port conflict
            if self._mongod_proc.returncode == 48:
                raise RuntimeError(
                    f"mongod port {port} is already in use (likely from parallel test execution). "
                    f"Try using a different port or ensure previous mongod processes are cleaned up."
                )
            # Exit code 100 means data directory issue (lock, corruption, or incompatible version)
            if self._mongod_proc.returncode == 100:
                raise RuntimeError(
                    f"mongod data directory issue at {db_path} (exit code 100). "
                    f"This usually means the directory is locked by another mongod process or corrupted. "
                    f"Error output: {error_output[:500]}"
                )
            raise RuntimeError(
                f"mongod process exited with code {self._mongod_proc.returncode}. Error output: {error_output[:500]}"
            )
        stderr_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to start local mongod (timeout after {max_attempts * 0.2}s)")

    def _can_connect(self, uri: str) -> bool:
        try:
            client: MongoClient[Any] = MongoClient(uri, serverSelectionTimeoutMS=500)
            client.server_info()
            client.close()
            return True
        except Exception:
            return False

    @staticmethod
    def _parse_host_port(uri: str) -> tuple[str, int]:
        parsed = parse_uri(uri)
        if not parsed.get("nodelist"):
            raise RuntimeError("database.uri must include host:port when local=true")
        host, port = parsed["nodelist"][0]
        if port is None:
            port = 27017
        return host, port
