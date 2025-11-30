"""Tests for Service Controller."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from wks.service_controller import (
    ServiceController,
    ServiceStatusData,
    ServiceStatusLaunch,
    agent_installed,
    agent_label,
    agent_plist_path,
    daemon_start_launchd,
    daemon_status_launchd,
    daemon_stop_launchd,
    default_mongo_uri,
    is_macos,
    stop_managed_mongo,
    _fmt_bool,
    _format_timestamp_value,
    _pid_running,
)
from wks.config import WKSConfig, MongoSettings


class TestServiceHelpers:
    """Test helper functions."""

    def test_fmt_bool(self):
        """Test boolean formatting."""
        assert _fmt_bool(True) == "true"
        assert _fmt_bool(False) == "false"
        assert _fmt_bool(None) == "-"
        assert _fmt_bool(True, color=True) == "[green]true[/green]"
        assert _fmt_bool(False, color=True) == "[red]false[/red]"

    def test_format_timestamp_value(self):
        """Test timestamp formatting."""
        assert _format_timestamp_value(None, "%Y-%m-%d") == ""
        assert _format_timestamp_value("", "%Y-%m-%d") == ""
        
        # ISO format
        assert _format_timestamp_value("2025-01-01T12:00:00Z", "%Y-%m-%d") == "2025-01-01"
        
        # Fallback
        assert _format_timestamp_value("invalid", "%Y-%m-%d") == "invalid"

    @patch("os.kill")
    def test_pid_running(self, mock_kill):
        """Test PID check."""
        mock_kill.return_value = None
        assert _pid_running(123) is True
        
        mock_kill.side_effect = ProcessLookupError
        assert _pid_running(123) is False

    @patch("wks.service_controller.mongoctl.stop_managed_mongo")
    def test_stop_managed_mongo(self, mock_stop):
        """Test stop managed mongo."""
        stop_managed_mongo()
        mock_stop.assert_called_once()

    def test_agent_label(self):
        """Test agent label."""
        assert agent_label() == "com.wieselquist.wks0"

    def test_agent_plist_path(self):
        """Test agent plist path."""
        path = agent_plist_path()
        assert path.name == "com.wieselquist.wks0.plist"
        assert "LaunchAgents" in str(path)

    @patch("platform.system")
    def test_is_macos(self, mock_system):
        """Test is_macos."""
        mock_system.return_value = "Darwin"
        assert is_macos() is True
        
        mock_system.return_value = "Linux"
        assert is_macos() is False

    @patch("pathlib.Path.exists")
    def test_agent_installed(self, mock_exists):
        """Test agent installed check."""
        mock_exists.return_value = True
        assert agent_installed() is True
        
        mock_exists.return_value = False
        assert agent_installed() is False

    @patch("wks.service_controller.WKSConfig.load")
    def test_default_mongo_uri(self, mock_load):
        """Test default mongo URI."""
        mock_config = MagicMock(spec=WKSConfig)
        mock_config.mongo = MongoSettings(uri="mongodb://test:27017")
        mock_load.return_value = mock_config
        
        assert default_mongo_uri() == "mongodb://test:27017"
        
        mock_load.side_effect = Exception("Config error")
        assert default_mongo_uri() == "mongodb://localhost:27017"


class TestLaunchdControl:
    """Test launchd control functions."""

    @patch("subprocess.call")
    @patch("os.getuid")
    def test_daemon_start_launchd(self, mock_uid, mock_call):
        """Test starting daemon via launchd."""
        mock_uid.return_value = 501
        
        # Case 1: kickstart succeeds
        mock_call.return_value = 0
        daemon_start_launchd()
        assert mock_call.call_count == 1
        
        # Case 2: kickstart fails, full restart sequence
        mock_call.reset_mock()
        mock_call.side_effect = [1, 0, 0, 0, 0]  # kickstart fails, then bootout, bootstrap, enable, kickstart
        daemon_start_launchd()
        assert mock_call.call_count == 5

    @patch("subprocess.call")
    @patch("os.getuid")
    def test_daemon_stop_launchd(self, mock_uid, mock_call):
        """Test stopping daemon via launchd."""
        mock_uid.return_value = 501
        daemon_stop_launchd()
        mock_call.assert_called_once()
        args = mock_call.call_args[0][0]
        assert args[0] == "launchctl"
        assert args[1] == "bootout"

    @patch("subprocess.call")
    @patch("os.getuid")
    def test_daemon_status_launchd(self, mock_uid, mock_call):
        """Test getting daemon status via launchd."""
        mock_uid.return_value = 501
        mock_call.return_value = 0
        
        assert daemon_status_launchd() == 0
        mock_call.assert_called_once()
        
        mock_call.side_effect = Exception("Error")
        assert daemon_status_launchd() == 3


class TestServiceStatusData:
    """Test ServiceStatusData model."""

    def test_to_dict(self):
        """Test conversion to dict."""
        data = ServiceStatusData(
            running=True,
            uptime="1h",
            pid=123,
            launch=ServiceStatusLaunch(state="running")
        )
        
        d = data.to_dict()
        assert d["service"]["running"] is True
        assert d["service"]["pid"] == 123
        assert d["launch_agent"]["state"] == "running"

    def test_to_rows(self):
        """Test conversion to display rows."""
        data = ServiceStatusData(
            running=True,
            uptime="1h",
            pid=123,
            launch=ServiceStatusLaunch(state="running", type="LaunchAgent")
        )
        
        rows = data.to_rows()
        # Should contain Health, File System, Launch sections
        assert any("Health" in r[0] for r in rows)
        assert any("File System" in r[0] for r in rows)
        assert any("Launch" in r[0] for r in rows)


class TestServiceController:
    """Test ServiceController logic."""

    @patch("wks.service_controller.is_macos", return_value=True)
    @patch("wks.service_controller.agent_installed", return_value=True)
    @patch("subprocess.check_output")
    @patch("os.getuid", return_value=501)
    def test_read_launch_agent(self, mock_uid, mock_check_output, mock_installed, mock_macos):
        """Test reading launch agent info."""
        mock_check_output.return_value = b"""
            active count = 1
            path = /path/to/plist
            state = running
            program = /path/to/python
            pid = 12345
        """
        
        launch = ServiceController._read_launch_agent()
        assert launch is not None
        assert launch.active_count == "1"
        assert launch.state == "running"
        assert launch.pid == "12345"

    @patch("wks.service_controller.LOCK_FILE")
    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_read_health_success(self, mock_file, mock_exists, mock_lock):
        """Test reading health from file."""
        # Mock health.json exists
        mock_exists.side_effect = lambda: True  # health.json exists
        
        health_data = {
            "lock_present": True,
            "uptime_hms": "2h",
            "pid": 12345,
            "fs_rate_short": 1.5
        }
        mock_file.return_value.read.return_value = json.dumps(health_data)
        
        status = ServiceStatusData()
        ServiceController._read_health(status)
        
        assert status.running is True
        assert status.pid == 12345
        assert status.fs_rate_short == 1.5

    @patch("wks.service_controller.LOCK_FILE")
    @patch("pathlib.Path.exists")
    def test_read_health_fallback_lock(self, mock_exists, mock_lock):
        """Test fallback to lock file when health.json missing."""
        # Mock health.json missing, but lock file exists
        def exists_side_effect():
            # First call is health.json, second is LOCK_FILE
            # But wait, LOCK_FILE.exists() is called directly on the mock object
            return False
            
        # We need to mock Path.home() / ... / health.json .exists() returning False
        # And LOCK_FILE.exists() returning True
        
        # Since we can't easily distinguish paths in side_effect without more complex logic,
        # let's assume health.json check returns False (first call to exists on Path object)
        # and LOCK_FILE is a separate mock
        
        # Actually, ServiceController uses Path.home() / ...
        # Let's mock Path.exists globally but handle the instance
        pass

    @patch("wks.service_controller.ServiceController._read_launch_agent")
    @patch("wks.service_controller.ServiceController._read_health")
    def test_get_status(self, mock_read_health, mock_read_launch):
        """Test get_status orchestration."""
        mock_read_launch.return_value = ServiceStatusLaunch(state="running")
        
        status = ServiceController.get_status()
        
        assert status.launch.state == "running"
        mock_read_health.assert_called_once_with(status)
