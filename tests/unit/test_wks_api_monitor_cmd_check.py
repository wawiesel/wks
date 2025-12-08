"""Unit tests for monitor cmd_check."""

from unittest.mock import MagicMock, patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor.cmd_check import cmd_check

pytestmark = pytest.mark.monitor


def test_cmd_check_reports_monitored(monkeypatch):
    """Test cmd_check reports when path is monitored."""
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.database.DatabaseConfig import DatabaseConfig

    monitor_cfg = MonitorConfig(
        filter={},
        priority={"dirs": {}, "weights": {}},
        database="monitor",
        sync={
            "max_documents": 1000000,
            "min_priority": 0.0,
            "prune_interval_secs": 300.0,
        },
    )

    mock_config = MagicMock()
    mock_config.monitor = monitor_cfg
    mock_config.database = DatabaseConfig(type="mongomock", prefix="wks", data={})

    with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
        with patch("wks.api.monitor.cmd_check.explain_path", return_value=(True, ["Included by rule"])):
            with patch("wks.api.monitor.cmd_check.calculate_priority", return_value=5):
                result = run_cmd(cmd_check, path="/tmp/demo.txt")

    assert result.output["is_monitored"] is True
    assert "priority" in result.result
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_check_path_not_exists(monkeypatch):
    """Test cmd_check when path doesn't exist."""
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.database.DatabaseConfig import DatabaseConfig

    monitor_cfg = MonitorConfig(
        filter={},
        priority={"dirs": {}, "weights": {}},
        database="monitor",
        sync={
            "max_documents": 1000000,
            "min_priority": 0.0,
            "prune_interval_secs": 300.0,
        },
    )

    mock_config = MagicMock()
    mock_config.monitor = monitor_cfg
    mock_config.database = DatabaseConfig(type="mongomock", prefix="wks", data={})

    # Mock explain_path to return False
    monkeypatch.setattr("wks.api.monitor.cmd_check.explain_path", lambda _cfg, _path: (False, ["Excluded by rule"]))

    with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
        result = run_cmd(cmd_check, path="/nonexistent/path.txt")

    assert result.output["is_monitored"] is False
    assert result.output["priority"] is None
    assert "⚠" in result.output["decisions"][0]["symbol"]  # Path doesn't exist symbol
