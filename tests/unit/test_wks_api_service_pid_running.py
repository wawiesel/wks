"""Unit tests for wks.api.service._pid_running."""

from unittest.mock import patch

from wks.api.service._pid_running import _pid_running


def test_pid_running_exists():
    """Test _pid_running returns True when process exists."""
    with patch("os.kill") as mock_kill:
        assert _pid_running(123) is True
        mock_kill.assert_called_once_with(123, 0)


def test_pid_running_not_exists():
    """Test _pid_running returns False when process does not exist."""
    with patch("os.kill", side_effect=OSError("Process not found")):
        assert _pid_running(456) is False
