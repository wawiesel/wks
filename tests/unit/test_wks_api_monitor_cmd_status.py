"""Unit tests for wks.api.monitor.cmd_status module."""

from types import SimpleNamespace

import pytest

from tests.unit.conftest import DummyConfig
from wks.api.monitor import cmd_status

pytestmark = pytest.mark.monitor


def test_cmd_status_mongodb_error(monkeypatch):
    """Test cmd_status when MongoDB connection fails."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Mock DatabaseCollection to raise exception on __enter__
    class MockDatabaseCollection:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            raise Exception("Connection failed")

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("wks.api.monitor.cmd_status.DatabaseCollection", MockDatabaseCollection)

    result = cmd_status.cmd_status()
    assert result.output["tracked_files"] == 0
    assert result.output["success"] is True  # No issues if no priority dirs


def test_cmd_status_sets_success_based_on_issues(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"/invalid/path": 100.0}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Mock explain_path to return False for invalid path
    def mock_explain_path(_cfg, path):
        if str(path) == "/invalid/path":
            return False, ["Excluded by rules"]
        return True, []

    monkeypatch.setattr("wks.api.monitor.cmd_status.explain_path", mock_explain_path)

    # Mock DatabaseCollection
    class MockDatabaseCollection:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def count_documents(self, *args, **kwargs):
            return 0

    monkeypatch.setattr("wks.api.monitor.cmd_status.DatabaseCollection", MockDatabaseCollection)

    result = cmd_status.cmd_status()
    assert result.output["issues"] == ["Priority directory invalid: /invalid/path (Excluded by rules)"]
    assert result.output["success"] is False
