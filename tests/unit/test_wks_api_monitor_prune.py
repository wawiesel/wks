"""Unit tests for wks.api.monitor.prune."""

from unittest.mock import MagicMock

from wks.api.monitor.prune import prune


def test_monitor_prune_removes_missing_files(monkeypatch):
    """Test that missing files are removed from DB."""
    # Mock Config
    mock_config = MagicMock()

    # Mock DB
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__enter__.return_value = mock_collection

    # Database(config...) returns context manager
    monkeypatch.setattr("wks.api.monitor.prune.Database", lambda c, n: mock_db)

    # Mock find result
    docs = [
        {"_id": "1", "local_uri": "file:///tmp/exists"},
        {"_id": "2", "local_uri": "file:///tmp/missing"},
    ]
    mock_collection.find.return_value = docs

    # Mock uri_to_path
    mock_path_exists = MagicMock()
    mock_path_exists.exists.return_value = True

    mock_path_missing = MagicMock()
    mock_path_missing.exists.return_value = False

    def side_effect(uri):
        if "missing" in uri:
            return mock_path_missing
        return mock_path_exists

    mock_uri = MagicMock()

    def uri_side_effect(uri_str):
        m = MagicMock()
        m.path = side_effect(uri_str)
        return m

    mock_uri.side_effect = uri_side_effect

    monkeypatch.setattr("wks.api.monitor.prune.URI", mock_uri)

    result = prune(mock_config)

    # Should delete ID 2
    mock_collection.delete_many.assert_called_with({"_id": {"$in": ["2"]}})
    assert result["deleted_count"] == mock_collection.delete_many.return_value


def test_monitor_prune_handles_os_error(monkeypatch):
    """Test graceful handling of FS errors."""
    mock_config = MagicMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__enter__.return_value = mock_collection
    monkeypatch.setattr("wks.api.monitor.prune.Database", lambda c, n: mock_db)

    mock_collection.find.return_value = [{"_id": "1", "local_uri": "file:///error"}]

    mock_uri = MagicMock()
    mock_uri.return_value.path.exists.side_effect = OSError("Disk error")
    monkeypatch.setattr("wks.api.monitor.prune.URI", mock_uri)

    result = prune(mock_config)

    # Should not delete
    mock_collection.delete_many.assert_not_called()
    assert len(result["warnings"]) == 1
    assert "Disk error" in result["warnings"][0]
