"""Tests for wks/service_controller.py - ServiceController and related functions."""

import json
import subprocess
from unittest.mock import MagicMock, mock_open, patch

import pytest

from wks.config import MongoSettings, WKSConfig
from wks.service_controller import (
    ServiceController,
    ServiceStatusData,
    ServiceStatusLaunch,
    _pid_running,
    agent_installed,
    agent_label,
    agent_plist_path,
    daemon_start_launchd,
    daemon_status_launchd,
    daemon_stop_launchd,
    default_mongo_uri,
    is_macos,
    stop_managed_mongo,
)


@pytest.mark.integration
class TestServiceHelpers:
    """Test helper functions."""

    def test_stop_managed_mongo(self):
        """Test stop_managed_mongo is callable (no-op currently)."""
        stop_managed_mongo()  # Just ensure it doesn't raise

    @patch("os.kill")
    def test_pid_running(self, mock_kill):
        """Test PID check."""
        mock_kill.return_value = None
        assert _pid_running(123) is True

        mock_kill.side_effect = ProcessLookupError
        assert _pid_running(123) is False

    def test_agent_label(self):
        """Test agent label."""
        assert agent_label() == "com.wieselquist.wksc"

    def test_agent_plist_path(self):
        """Test agent plist path."""
        path = agent_plist_path()
        assert path.name == "com.wieselquist.wksc.plist"
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


@pytest.mark.integration
class TestLaunchctl:
    """Test _launchctl helper."""

    @patch("subprocess.call")
    def test_launchctl_success(self, mock_call):
        """Test successful launchctl call."""
        from wks.service_controller import _launchctl

        mock_call.return_value = 0
        assert _launchctl("status") == 0

    @patch("subprocess.call")
    def test_launchctl_not_found(self, mock_call):
        """Test when launchctl binary not found."""
        from wks.service_controller import _launchctl

        mock_call.side_effect = FileNotFoundError
        assert _launchctl("status") == 2


@pytest.mark.integration
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
        mock_call.side_effect = [
            1,
            0,
            0,
            0,
            0,
        ]  # kickstart fails, then bootout, bootstrap, enable, kickstart
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


@pytest.mark.integration
class TestServiceStatusLaunch:
    """Test ServiceStatusLaunch model."""

    def test_present_true(self):
        """Test present() returns True when fields set."""
        launch = ServiceStatusLaunch(state="running")
        assert launch.present() is True

    def test_present_false(self):
        """Test present() returns False when no fields set."""
        launch = ServiceStatusLaunch()
        assert launch.present() is False

    def test_as_dict(self):
        """Test conversion to dict."""
        launch = ServiceStatusLaunch(state="running", pid="123")
        d = launch.as_dict()
        assert d["state"] == "running"
        assert d["pid"] == "123"


@pytest.mark.integration
class TestServiceStatusData:
    """Test ServiceStatusData model."""

    def test_to_dict(self):
        """Test conversion to dict."""
        data = ServiceStatusData(running=True, uptime="1h", pid=123, launch=ServiceStatusLaunch(state="running"))

        d = data.to_dict()
        assert d["service"]["running"] is True
        assert d["service"]["pid"] == 123
        assert d["launch_agent"]["state"] == "running"


@pytest.mark.integration
class TestServiceController:
    """Test ServiceController logic."""

    @patch("wks.service_controller.is_macos", return_value=True)
    @patch("wks.service_controller.agent_installed", return_value=True)
    @patch("subprocess.check_output")
    @patch("os.getuid", return_value=501)
    def test_read_launch_agent(self, mock_uid, mock_check_output, mock_installed, mock_macos):  # noqa: ARG002
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

    @patch("wks.service_controller.is_macos", return_value=True)
    @patch("wks.service_controller.agent_installed", return_value=True)
    @patch("subprocess.check_output")
    @patch("os.getuid", return_value=501)
    def test_read_launch_agent_with_arguments(self, mock_uid, mock_check_output, mock_installed, mock_macos):  # noqa: ARG002
        """Test reading launch agent with arguments block."""
        mock_check_output.return_value = b"""
            active count = 1
            state = running
            arguments = {
                /usr/bin/python3
                -m
                wks
            }
        """

        launch = ServiceController._read_launch_agent()
        assert launch is not None
        assert launch.arguments == "/usr/bin/python3 -m wks"

    @patch("wks.service_controller.LOCK_FILE")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_read_health_success(self, mock_file, mock_exists, mock_lock):  # noqa: ARG002
        """Test reading health from file."""
        # Mock health.json exists
        mock_exists.side_effect = lambda: True  # health.json exists

        health_data = {"lock_present": True, "uptime_hms": "2h", "pid": 12345, "fs_rate_short": 1.5}
        mock_file.return_value.read.return_value = json.dumps(health_data)

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.running is True
        assert status.pid == 12345
        assert status.fs_rate_short == 1.5

    def test_read_health_lock_file_fallback(self, tmp_path, monkeypatch):
        """Test fallback to lock file when health.json missing."""
        import wks.service_controller as sc

        # No health.json exists
        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))

        # Create lock file with PID
        lock_file = tmp_path / "daemon.lock"
        lock_file.write_text("99999\n")  # Non-existent PID
        monkeypatch.setattr(sc, "LOCK_FILE", lock_file)

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.lock is True
        assert status.pid == 99999
        assert status.running is False  # PID doesn't exist

    def test_read_health_no_lock_file(self, tmp_path, monkeypatch):
        """Test when neither health.json nor lock file exists."""
        import wks.service_controller as sc

        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))
        lock_file = tmp_path / "daemon.lock"
        monkeypatch.setattr(sc, "LOCK_FILE", lock_file)

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.lock is False
        assert status.running is False
        assert "not running" in status.notes[0]

    def test_read_health_bad_lock_file(self, tmp_path, monkeypatch):
        """Test when lock file has bad content."""
        import wks.service_controller as sc

        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))
        lock_file = tmp_path / "daemon.lock"
        lock_file.write_text("not a number\n")
        monkeypatch.setattr(sc, "LOCK_FILE", lock_file)

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.lock is True
        assert "PID unavailable" in status.notes[0]

    def test_read_health_from_json(self, tmp_path, monkeypatch):
        """Test reading health from health.json."""
        import wks.service_controller as sc

        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))

        health_data = {
            "lock_present": True,
            "uptime_hms": "2h 30m",
            "pid": 12345,
            "pending_deletes": 5,
            "pending_mods": 10,
            "last_error": None,
            "fs_rate_short": 1.5,
            "fs_rate_long": 0.5,
            "fs_rate_weighted": 1.0,
        }
        health_path = tmp_path / "health.json"
        health_path.write_text(json.dumps(health_data))

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.running is True
        assert status.pid == 12345
        assert status.ok is True
        assert status.fs_rate_short == 1.5

    def test_read_health_json_with_bad_pid(self, tmp_path, monkeypatch):
        """Test health.json with non-integer pid."""
        import wks.service_controller as sc

        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))

        health_data = {"lock_present": True, "pid": "not_a_number"}
        health_path = tmp_path / "health.json"
        health_path.write_text(json.dumps(health_data))

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.pid is None

    def test_read_health_json_with_last_error(self, tmp_path, monkeypatch):
        """Test health.json with last_error set."""
        import wks.service_controller as sc

        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))

        health_data = {"lock_present": True, "last_error": "Something went wrong"}
        health_path = tmp_path / "health.json"
        health_path.write_text(json.dumps(health_data))

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.ok is False
        assert status.last_error == "Something went wrong"

    def test_read_health_json_with_bad_rate(self, tmp_path, monkeypatch):
        """Test health.json with invalid fs_rate values."""
        import wks.service_controller as sc

        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))

        health_data = {"lock_present": True, "fs_rate_short": "invalid"}
        health_path = tmp_path / "health.json"
        health_path.write_text(json.dumps(health_data))

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert status.fs_rate_short is None

    def test_read_health_json_parse_error(self, tmp_path, monkeypatch):
        """Test when health.json contains invalid JSON."""
        import wks.service_controller as sc

        monkeypatch.setattr(sc, "WKS_HOME_EXT", str(tmp_path))

        health_path = tmp_path / "health.json"
        health_path.write_text("not valid json {")

        status = ServiceStatusData()
        ServiceController._read_health(status)

        assert "Failed to read health metrics" in status.notes[0]

    @patch("wks.service_controller.ServiceController._read_launch_agent")
    @patch("wks.service_controller.ServiceController._read_health")
    def test_get_status(self, mock_read_health, mock_read_launch):
        """Test get_status orchestration."""
        mock_read_launch.return_value = ServiceStatusLaunch(state="running")

        status = ServiceController.get_status()

        assert status.launch.state == "running"
        mock_read_health.assert_called_once_with(status)

    @patch("wks.service_controller.is_macos", return_value=False)
    @patch("wks.service_controller.ServiceController._read_health")
    def test_read_launch_agent_not_macos(self, mock_health, mock_macos):  # noqa: ARG002
        """Test _read_launch_agent returns None on non-macOS."""
        result = ServiceController._read_launch_agent()
        assert result is None

    @patch("wks.service_controller.is_macos", return_value=True)
    @patch("wks.service_controller.agent_installed", return_value=True)
    @patch("subprocess.check_output")
    @patch("os.getuid", return_value=501)
    def test_read_launch_agent_exception(self, mock_uid, mock_check, mock_installed, mock_macos):  # noqa: ARG002
        """Test _read_launch_agent returns None on exception."""
        mock_check.side_effect = subprocess.CalledProcessError(1, "launchctl")
        result = ServiceController._read_launch_agent()
        assert result is None

    @patch("wks.service_controller.is_macos", return_value=True)
    @patch("wks.service_controller.agent_installed", return_value=True)
    @patch("wks.service_controller.ServiceController._read_health")
    def test_get_status_with_agent_error(self, mock_health, mock_installed, mock_macos):  # noqa: ARG002
        """Test get_status adds note when launch agent unavailable."""
        with patch.object(ServiceController, "_read_launch_agent", return_value=None):
            status = ServiceController.get_status()
            assert "Launch agent status unavailable" in status.notes
