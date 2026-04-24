import json
from unittest.mock import MagicMock

from wks.api.log.summarize_status_log_messages import STATUS_LOG_MESSAGE_LIMIT
from wks.api.service._read_daemon_file import _read_daemon_file


def test_read_daemon_file_file_not_exists(tmp_path):
    f = tmp_path / "daemon.json"
    result = _read_daemon_file(f)
    assert result == {"warnings": [], "errors": []}


def test_read_daemon_file_valid(tmp_path):
    f = tmp_path / "daemon.json"
    data = {"warnings": ["w1"], "errors": ["e1"], "pid": 123}
    f.write_text(json.dumps(data))

    result = _read_daemon_file(f)
    assert result == data


def test_read_daemon_file_summarizes_large_message_lists(tmp_path):
    f = tmp_path / "daemon.json"
    warnings = [f"warn-{idx}" for idx in range(STATUS_LOG_MESSAGE_LIMIT + 5)]
    errors = [f"error-{idx}" for idx in range(STATUS_LOG_MESSAGE_LIMIT + 1)]
    data = {"warnings": warnings, "errors": errors, "pid": 123}
    f.write_text(json.dumps(data))

    result = _read_daemon_file(f)

    assert result["pid"] == 123
    assert len(result["warnings"]) == STATUS_LOG_MESSAGE_LIMIT + 1
    assert len(result["errors"]) == STATUS_LOG_MESSAGE_LIMIT + 1
    assert "showing 20 most recent warnings out of 25 total" in result["warnings"][0]
    assert "showing 20 most recent errors out of 21 total" in result["errors"][0]
    assert result["warnings"][1:] == warnings[-STATUS_LOG_MESSAGE_LIMIT:]
    assert result["errors"][1:] == errors[-STATUS_LOG_MESSAGE_LIMIT:]


def test_read_daemon_file_corrupt_json(tmp_path):
    f = tmp_path / "daemon.json"
    f.write_text("{invalid")

    result = _read_daemon_file(f)
    assert "warnings" in result
    assert "errors" in result
    assert len(result["errors"]) == 1
    assert "Failed to read daemon file" in result["errors"][0]


def test_read_daemon_file_os_error(tmp_path):
    f = tmp_path / "daemon.json"
    f.touch()  # Create it so exists() passes

    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = OSError("Access denied")

    result = _read_daemon_file(mock_path)
    assert len(result["errors"]) == 1
    assert "Access denied" in result["errors"][0]
