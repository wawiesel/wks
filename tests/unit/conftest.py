"""Shared test fixtures for unit tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from wks.api.database.DatabaseConfig import DatabaseConfig


class DummyConfig:
    """Mock WKSConfig for testing."""

    def __init__(self, monitor):
        self.monitor = monitor
        self.save_calls = 0

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
    config = MagicMock()
    config.database = DatabaseConfig(type="mongomock", prefix="wks", data={})
    return config


def run_cmd(cmd_func, *args, **kwargs):
    """Execute a cmd function and return the result with progress_callback executed."""
    result = cmd_func(*args, **kwargs)
    list(result.progress_callback(result))
    return result


@pytest.fixture
def patch_wks_config(monkeypatch, mock_config):
    """Patch WKSConfig.load to return mock_config."""
    with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
        yield mock_config
