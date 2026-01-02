"""Tests for wks/utils/has_internet.py."""

from unittest.mock import patch

from wks.utils.has_internet import has_internet


def test_has_internet_returns_true_on_success():
    """Test has_internet returns True when connection succeeds."""
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect.return_value = None
        assert has_internet() is True


def test_has_internet_returns_false_on_oserror():
    """Test has_internet returns False when connection fails."""
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect.side_effect = OSError("No route")
        assert has_internet() is False


def test_has_internet_accepts_custom_params():
    """Test has_internet accepts custom host/port/timeout."""
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect.return_value = None
        result = has_internet(host="1.1.1.1", port=443, timeout=5)
        assert result is True
