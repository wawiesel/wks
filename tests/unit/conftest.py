"""Shared test fixtures for unit tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from wks.api.database.DatabaseConfig import DatabaseConfig


class DummyConfig:
    """Mock WKSConfig for testing."""

    def __init__(self, monitor=None, database=None, daemon=None):
        from wks.api.monitor.MonitorConfig import MonitorConfig
        from wks.api.database.DatabaseConfig import DatabaseConfig

        self.monitor = monitor or MonitorConfig(
            filter={},
            priority={"dirs": {}, "weights": {}},
            database="monitor",
            sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
        )
        self.database = database or DatabaseConfig(type="mongomock", prefix="wks", data={})
        self.daemon = daemon
        self.save_calls = 0
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def save(self):
        self.save_calls += 1


class MockDatabaseCollection:
    """Mock DatabaseCollection for testing."""

    def __init__(self, *args, **kwargs):
        self.find_one_result = None
        self.update_one_calls = []
        self.count_documents_result = 0
        self.find_result = []
        self.delete_many_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def find_one(self, filter, projection=None):
        return self.find_one_result

    def update_one(self, filter, update, upsert=False):
        self.update_one_calls.append({"filter": filter, "update": update, "upsert": upsert})

    def count_documents(self, filter=None):
        return self.count_documents_result

    def find(self, filter=None, projection=None):
        # Return a mock cursor that supports .sort().limit()
        class MockCursor:
            def __init__(self, data):
                self.data = data

            def sort(self, *args, **kwargs):
                return self

            def limit(self, n):
                return self.data[:n]

            def __iter__(self):
                return iter(self.data)

        return MockCursor(self.find_result)

    def delete_many(self, filter):
        self.delete_many_calls.append(filter)
        return SimpleNamespace(deleted_count=len(self.find_result))


@pytest.fixture
def mock_config():
    """Create a minimal mock WKSConfig."""
    return DummyConfig()


def run_cmd(cmd_func, *args, **kwargs):
    """Execute a cmd function and return the result with progress_callback executed."""
    result = cmd_func(*args, **kwargs)
    list(result.progress_callback(result))
    return result


@pytest.fixture
def patch_wks_config(monkeypatch):
    """Patch WKSConfig.load to return a DummyConfig instance."""
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.database.DatabaseConfig import DatabaseConfig

    config = DummyConfig(
        monitor=MonitorConfig(
            filter={},
            priority={"dirs": {}, "weights": {}},
            database="monitor",
            sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
        ),
        database=DatabaseConfig(type="mongomock", prefix="wks", data={}),
    )
    monkeypatch.setattr(WKSConfig, "load", lambda: config)
    return config
