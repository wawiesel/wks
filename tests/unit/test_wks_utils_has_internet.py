from unittest.mock import patch

from wks.api.config.has_internet import has_internet


def test_has_internet_returns_true_on_success():
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect.return_value = None
        assert has_internet() is True


def test_has_internet_returns_false_on_oserror():
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect.side_effect = OSError("No route")
        assert has_internet() is False


def test_has_internet_accepts_custom_params():
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect.return_value = None
        result = has_internet(host="1.1.1.1", port=443, timeout=5)
        assert result is True
