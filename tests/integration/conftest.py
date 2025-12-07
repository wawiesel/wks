"""Shared fixtures for integration tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from wks.api.config import (
    DisplayConfig,
    MetricsConfig,
    WKSConfig,
)
from wks.api.monitor.MonitorConfig import MonitorConfig
from wks.api.transform.config import TransformConfig
from wks.api.vault.config import VaultConfig


class FakeCollection:
    """Fake MongoDB collection for testing."""

    def __init__(self):
        self.docs = {}
        self.deleted = []

    def count_documents(self, filt, limit=None):  # noqa: ARG002
        path = filt.get("path") if isinstance(filt, dict) else None
        if path:
            if isinstance(path, dict) and "$in" in path:
                return sum(1 for candidate in path["$in"] if candidate in self.docs)
            if isinstance(path, str):
                return 1 if path in self.docs else 0
        return len(self.docs)

    def find_one(self, filt, projection=None):
        path = filt.get("path") if isinstance(filt, dict) else None
        if not isinstance(path, str):
            return None
        doc = self.docs.get(path)
        if not doc:
            return None
        if projection:
            return {key: doc.get(key) for key in projection if key in doc}
        return doc

    def update_one(self, filt, update, upsert=False):  # noqa: ARG002
        path = filt.get("path") if isinstance(filt, dict) else None
        if not isinstance(path, str):
            return
        doc = update.get("$set", {})
        self.docs[path] = dict(doc)

    def delete_one(self, filt):
        path = filt.get("path") if isinstance(filt, dict) else None
        if isinstance(path, str):
            self.docs.pop(path, None)
            self.deleted.append(path)

    def find(self, filt, projection=None):  # noqa: ARG002
        return iter([])

    def delete_many(self, filt):
        pass


class FakeVault:
    """Fake vault for testing."""

    def __init__(self, *args, **kwargs):  # noqa: ARG002
        self.vault_path = kwargs.get("vault_path", Path("/tmp/test_vault"))
        self.links_dir = kwargs.get("links_dir")

    def ensure_structure(self):
        pass

    def log_file_operation(self, *args, **kwargs):
        pass

    def update_link_on_move(self, *args, **kwargs):
        pass

    def update_vault_links_on_move(self, *args, **kwargs):
        pass

    def mark_reference_deleted(self, *args, **kwargs):
        pass

    def create_project_note(self, *args, **kwargs):
        pass


class FakeIndexer:
    """Fake vault indexer for testing."""

    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_config(cls, vault, cfg):  # noqa: ARG003
        return cls()

    def sync(self, incremental=False):
        pass

    def update_links_on_file_move(self, old_uri, new_uri):  # noqa: ARG002
        return 0

    def has_references_to(self, path):  # noqa: ARG002
        return False


class FakeObserver:
    """Fake filesystem observer for testing."""

    def stop(self):
        pass

    def join(self):
        pass


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB connection for integration tests."""
    return FakeCollection()


@pytest.fixture
def temp_watch_directory(tmp_path):
    """Create a temporary directory with test files."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    (watch_dir / "test.txt").write_text("test content")
    return watch_dir


@pytest.fixture
def daemon_config(tmp_path):
    """Create a valid daemon configuration."""
    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "include_paths": [str(tmp_path)],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {str(tmp_path): 100},
                "touch_weight": 0.5,
                "database": "wks.monitor",
                "max_documents": 1000000,
                "priority": {},
                "prune_interval_secs": 300.0,
            }
        }
    )
    vault_cfg = VaultConfig(
        base_dir=str(tmp_path),
        wks_dir="WKS",
        update_frequency_seconds=10,
        database="wks.vault",
        vault_type="obsidian",
    )
    from wks.api.db._mongo.MongoDbConfig import MongoDbConfig

    mongo_cfg = MongoDbConfig(uri="mongodb://localhost:27017/")
    display_cfg = DisplayConfig()
    from wks.api.transform.config import CacheConfig

    transform_cfg = TransformConfig(
        cache=CacheConfig(location=Path(".wks/cache"), max_size_bytes=1024 * 1024 * 100),
        engines={},
        database="wks.transform",
    )
    metrics_cfg = MetricsConfig()

    return WKSConfig(
        monitor=monitor_cfg,
        vault=vault_cfg,
        db=mongo_cfg,
        display=display_cfg,
        transform=transform_cfg,
        metrics=metrics_cfg,
    )


@pytest.fixture
def mock_daemon_dependencies(monkeypatch):
    """Mock all daemon dependencies."""
    from wks.api.service import daemon as daemon_mod

    # Mock vault and indexer
    monkeypatch.setattr(daemon_mod, "ObsidianVault", FakeVault)
    monkeypatch.setattr(daemon_mod, "VaultLinkIndexer", FakeIndexer)

    # Mock MongoGuard
    class MockMongoGuard:
        def __init__(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(daemon_mod, "MongoGuard", MockMongoGuard)

    # Mock ensure_mongo_running if it exists
    if hasattr(daemon_mod, "ensure_mongo_running"):
        monkeypatch.setattr(daemon_mod, "ensure_mongo_running", lambda *_a, **_k: None)

    # Mock MCPBroker
    mock_broker = MagicMock()
    mock_broker.start = MagicMock()
    mock_broker.stop = MagicMock()
    monkeypatch.setattr(daemon_mod, "MCPBroker", lambda *_a, **_k: mock_broker)

    # Mock start_monitoring
    mock_observer = FakeObserver()
    monkeypatch.setattr(daemon_mod, "start_monitoring", lambda *_a, **_k: mock_observer)

    # Mock db_activity functions
    monkeypatch.setattr(daemon_mod, "load_db_activity_summary", lambda: None)
    monkeypatch.setattr(daemon_mod, "load_db_activity_history", lambda *_a: [])
