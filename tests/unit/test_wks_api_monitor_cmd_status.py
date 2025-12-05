"""Unit tests for wks.api.monitor.cmd_status module."""

import pytest
from types import SimpleNamespace

from wks.api.monitor import cmd_status
from tests.unit.conftest import DummyConfig
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

    # Mock MongoDB connection to raise exception
    def mock_connect(*args, **kwargs):
        raise Exception("Connection failed")

    monkeypatch.setattr("wks.api.monitor.cmd_status.connect_to_mongo", mock_connect)

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
    monkeypatch.setattr("wks.api.monitor.cmd_status.parse_database_key", lambda _key: ("db", "coll"))

    # Mock MongoDB client with proper structure
    mock_collection = SimpleNamespace(count_documents=lambda *args, **kwargs: 0)
    mock_db = SimpleNamespace()
    mock_db.__getitem__ = lambda _key: mock_collection
    mock_client = SimpleNamespace()
    mock_client.__getitem__ = lambda _key: mock_db
    mock_client.close = lambda: None

    monkeypatch.setattr("wks.api.monitor.cmd_status.connect_to_mongo", lambda *args, **kwargs: mock_client)

    result = cmd_status.cmd_status()
    assert result.output["issues"] == ["Priority directory invalid: /invalid/path (Excluded by rules)"]
    assert result.output["success"] is False
