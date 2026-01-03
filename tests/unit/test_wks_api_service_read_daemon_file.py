"""Unit tests for wks.api.service._read_daemon_file."""

import json
from unittest.mock import MagicMock

from wks.api.service._read_daemon_file import _read_daemon_file


def test_read_daemon_file_file_not_exists(tmp_path):
    """Test reading non-existent file."""
    f = tmp_path / "daemon.json"
    result = _read_daemon_file(f)
    assert result == {"warnings": [], "errors": []}


def test_read_daemon_file_valid(tmp_path):
    """Test reading valid file."""
    f = tmp_path / "daemon.json"
    data = {"warnings": ["w1"], "errors": ["e1"], "pid": 123}
    f.write_text(json.dumps(data))

    result = _read_daemon_file(f)
    assert result == data


def test_read_daemon_file_corrupt_json(tmp_path):
    """Test reading corrupt JSON file."""
    f = tmp_path / "daemon.json"
    f.write_text("{invalid")

    result = _read_daemon_file(f)
    assert "warnings" in result
    assert "errors" in result
    assert len(result["errors"]) == 1
    assert "Failed to read daemon file" in result["errors"][0]


def test_read_daemon_file_os_error(tmp_path):
    """Test reading file with OS error (mocked)."""
    f = tmp_path / "daemon.json"
    f.touch()  # Create it so exists() passes

    # Mock read_text to raise OSError
    # We need to mock Path.read_text on the specific instance or patch Path
    # Easier to mock the path object passed in
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = OSError("Access denied")

    result = _read_daemon_file(mock_path)
    assert len(result["errors"]) == 1
    assert "Access denied" in result["errors"][0]
