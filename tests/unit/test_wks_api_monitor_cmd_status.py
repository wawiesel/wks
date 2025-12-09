"""Unit tests for monitor cmd_status."""

from unittest.mock import MagicMock, patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor.cmd_status import cmd_status

pytestmark = pytest.mark.monitor


def test_cmd_status_mongodb_error(monkeypatch):
    """Test cmd_status when MongoDB connection fails."""
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.database.DatabaseConfig import DatabaseConfig

    monitor_cfg = MonitorConfig(
        filter={},
        priority={"dirs": {}},
        database="monitor",
        sync={
            "max_documents": 1000000,
            "min_priority": 0.0,
            "prune_interval_secs": 300.0,
        },
    )

    mock_config = MagicMock()
    mock_config.monitor = monitor_cfg
    mock_config.database = DatabaseConfig(type="mongomock", prefix="wks", data={"uri": "mongomock://localhost:27017/"})

    with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
        with patch("wks.api.monitor.cmd_status.Database") as mock_database:
            mock_database.side_effect = Exception("Connection failed")
            result = run_cmd(cmd_status)

    assert result.output["tracked_files"] == 0
    assert result.success is True  # No issues if no priority dirs
    assert "errors" in result.output or "warnings" in result.output


def test_cmd_status_sets_success_based_on_issues(monkeypatch):
    """Test cmd_status sets success based on issues found."""
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.database.DatabaseConfig import DatabaseConfig
    from pathlib import Path

    monitor_cfg = MonitorConfig(
        filter={},
        priority={"dirs": {"/invalid/path": 100.0}},
        database="monitor",
        sync={
            "max_documents": 1000000,
            "min_priority": 0.0,
            "prune_interval_secs": 300.0,
        },
    )

    mock_config = MagicMock()
    mock_config.monitor = monitor_cfg
    mock_config.database = DatabaseConfig(type="mongomock", prefix="wks", data={"uri": "mongomock://localhost:27017/"})

    # Mock explain_path to return False for invalid path
    def mock_explain_path(_cfg, path):
        if str(path) == "/invalid/path":
            return False, ["Excluded by rules"]
        return True, []

    mock_database = MagicMock()
    mock_database.count_documents.return_value = 0
    mock_database.__enter__ = MagicMock(return_value=mock_database)
    mock_database.__exit__ = MagicMock(return_value=False)

    with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
        with patch("wks.api.monitor.cmd_status.Database", return_value=mock_database):
            with patch("wks.api.monitor.cmd_status.explain_path", mock_explain_path):
                result = run_cmd(cmd_status)

    assert len(result.output["issues"]) > 0
    assert "Priority directory invalid: /invalid/path" in result.output["issues"][0]
    assert result.success is False
