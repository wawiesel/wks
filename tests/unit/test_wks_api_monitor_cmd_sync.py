"""Unit tests for wks.api.monitor.cmd_sync module."""

import pytest
from types import SimpleNamespace

from wks.api.monitor import cmd_sync
from tests.unit.conftest import DummyConfig, MockDatabaseCollection
pytestmark = pytest.mark.monitor


def test_cmd_sync_path_not_exists(monkeypatch):
    """Test cmd_sync when path doesn't exist."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_sync.cmd_sync(path="/nonexistent/path", recursive=False)
    assert result.output["success"] is False
    assert result.output["files_synced"] == 0
    assert "does not exist" in result.output["message"]

def test_cmd_sync_invalid_database(monkeypatch, tmp_path):
    """Test cmd_sync with invalid database name (DatabaseCollection raises ValueError)."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Mock DatabaseCollection to raise ValueError in __init__ (simulating invalid format)
    class MockDatabaseCollectionError:
        def __init__(self, database_key):
            raise ValueError("Invalid database format")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", MockDatabaseCollectionError)
    
    # ValueError will propagate - DatabaseCollection raises in __init__ before context manager
    import pytest
    with pytest.raises(ValueError, match="Invalid database format"):
        cmd_sync.cmd_sync(path=str(test_file), recursive=False)

def test_cmd_sync_wraps_output(monkeypatch, tmp_path):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.api.monitor.cmd_sync.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Mock DatabaseCollection
    mock_collection = MockDatabaseCollection()
    mock_collection.find_one_result = None
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (True, []))
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.calculate_priority",
        lambda _path, _dirs, _weights: 1.0,
    )
    monkeypatch.setattr("wks.api.monitor.cmd_sync.file_checksum", lambda _path: "abc123")
    monkeypatch.setattr("wks.api.monitor.cmd_sync._enforce_monitor_db_limit", lambda *args, **kwargs: None)

    result = cmd_sync.cmd_sync(path=str(test_file), recursive=False)
    assert result.output["files_synced"] == 1
    assert result.success is True

def test_cmd_sync_recursive(monkeypatch, tmp_path):
    """Test cmd_sync with recursive=True."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Create test directory with files
    test_dir = tmp_path / "testdir"
    test_dir.mkdir()
    file1 = test_dir / "file1.txt"
    file1.write_text("content1")
    file2 = test_dir / "file2.txt"
    file2.write_text("content2")

    # Mock DatabaseCollection
    mock_collection = MockDatabaseCollection()
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (True, []))
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.calculate_priority",
        lambda _path, _dirs, _weights: 1.0,
    )
    monkeypatch.setattr("wks.api.monitor.cmd_sync.file_checksum", lambda _path: "abc123")
    monkeypatch.setattr("wks.api.monitor.cmd_sync._enforce_monitor_db_limit", lambda *args, **kwargs: None)

    result = cmd_sync.cmd_sync(path=str(test_dir), recursive=True)
    assert result.output["files_synced"] == 2
    assert result.success is True

def test_cmd_sync_directory_non_recursive(monkeypatch, tmp_path):
    """Test cmd_sync with directory (non-recursive) uses iterdir."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Create test directory with files
    test_dir = tmp_path / "testdir"
    test_dir.mkdir()
    file1 = test_dir / "file1.txt"
    file1.write_text("content1")
    file2 = test_dir / "file2.txt"
    file2.write_text("content2")

    # Mock DatabaseCollection
    mock_collection = MockDatabaseCollection()
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (True, []))
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.calculate_priority",
        lambda _path, _dirs, _weights: 1.0,
    )
    monkeypatch.setattr("wks.api.monitor.cmd_sync.file_checksum", lambda _path: "abc123")
    monkeypatch.setattr("wks.api.monitor.cmd_sync._enforce_monitor_db_limit", lambda *args, **kwargs: None)

    result = cmd_sync.cmd_sync(path=str(test_dir), recursive=False)
    assert result.output["files_synced"] == 2
    assert result.success is True

def test_cmd_sync_file_excluded_by_explain_path(monkeypatch, tmp_path):
    """Test cmd_sync when file is excluded by explain_path."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Mock DatabaseCollection
    mock_collection = MockDatabaseCollection()
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    # Mock explain_path to return False (excluded) - this should cause file to be skipped
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (False, ["Excluded"]))
    monkeypatch.setattr("wks.api.monitor.cmd_sync._enforce_monitor_db_limit", lambda *args, **kwargs: None)

    result = cmd_sync.cmd_sync(path=str(test_file), recursive=False)
    # File should be skipped because explain_path returns False
    assert result.output["files_synced"] == 0
    assert result.output["files_skipped"] == 1
    assert result.success is True

def test_cmd_sync_file_error_in_loop(monkeypatch, tmp_path):
    """Test cmd_sync when file processing raises exception."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Mock DatabaseCollection
    mock_collection = MockDatabaseCollection()
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (True, []))
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.calculate_priority",
        lambda _path, _dirs, _weights: 1.0,
    )
    # Mock file_checksum to raise exception (simulating file error)
    def raise_error(_path):
        raise Exception("File error")
    monkeypatch.setattr("wks.api.monitor.cmd_sync.file_checksum", raise_error)
    monkeypatch.setattr("wks.api.monitor.cmd_sync._enforce_monitor_db_limit", lambda *args, **kwargs: None)

    result = cmd_sync.cmd_sync(path=str(test_file), recursive=False)
    assert result.output["files_synced"] == 0
    assert result.output["files_skipped"] == 1
    assert len(result.output["errors"]) == 1
    assert "File error" in result.output["errors"][0]
    assert result.success is False

def test_cmd_sync_preserve_timestamp(monkeypatch, tmp_path):
    """Test cmd_sync preserves timestamp when checksum unchanged (hits line 113)."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    test_checksum = "abc123"
    existing_timestamp = "2024-01-01T00:00:00"

    # Mock DatabaseCollection
    mock_collection = MockDatabaseCollection()
    mock_collection.find_one_result = {"checksum": test_checksum, "timestamp": existing_timestamp}
    
    # Capture the update_one call to verify timestamp
    update_calls = []

    def capture_update_one(*args, **kwargs):
        update_calls.append({"args": args, "kwargs": kwargs})
        return None

    mock_collection.update_one = capture_update_one
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (True, []))
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.calculate_priority",
        lambda _path, _dirs, _weights: 1.0,
    )
    monkeypatch.setattr("wks.api.monitor.cmd_sync.file_checksum", lambda _path: test_checksum)
    monkeypatch.setattr("wks.api.monitor.cmd_sync._enforce_monitor_db_limit", lambda *args, **kwargs: None)

    result = cmd_sync.cmd_sync(path=str(test_file), recursive=False)
    assert result.output["files_synced"] == 1
    assert result.success is True
    # Verify timestamp was preserved (line 113)
    assert len(update_calls) == 1
    # update_one is called with filter as first arg, update dict as second arg
    update_dict = update_calls[0]["args"][1] if len(update_calls[0]["args"]) > 1 else update_calls[0]["kwargs"]
    assert "$set" in update_dict
    assert update_dict["$set"]["timestamp"] == existing_timestamp

def test_cmd_sync_enforce_db_limit(monkeypatch, tmp_path):
    """Test cmd_sync calls _enforce_monitor_db_limit."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.0, "max_documents": 100},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Mock DatabaseCollection - need to support _enforce_monitor_db_limit
    mock_collection = MockDatabaseCollection()
    mock_collection.find_one_result = None
    mock_collection.count_documents_result = 0
    mock_collection.find_result = []  # Empty - no docs to delete
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (True, []))
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.calculate_priority",
        lambda _path, _dirs, _weights: 1.0,
    )
    monkeypatch.setattr("wks.api.monitor.cmd_sync.file_checksum", lambda _path: "abc123")
    # Don't mock _enforce_monitor_db_limit - let it run

    result = cmd_sync.cmd_sync(path=str(test_file), recursive=False)
    assert result.output["files_synced"] == 1
    assert result.success is True
    # Verify _enforce_monitor_db_limit was called (it calls delete_many)
    # The function should have been called, but we can't easily verify without more complex mocking

def test_cmd_sync_below_min_priority(monkeypatch, tmp_path):
    """Test cmd_sync skips files below min_priority."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor", "min_priority": 0.5},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    cfg.mongo = SimpleNamespace(uri="mongodb://localhost:27017")
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Mock DatabaseCollection
    mock_collection = MockDatabaseCollection()
    
    monkeypatch.setattr("wks.api.monitor.cmd_sync.DatabaseCollection", lambda *args, **kwargs: mock_collection)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.explain_path", lambda _cfg, _path: (True, []))
    # Mock calculate_priority to return 0.3 (below min_priority of 0.5) - should be skipped
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.calculate_priority",
        lambda _path, _dirs, _weights: 0.3,
    )
    monkeypatch.setattr("wks.api.monitor.cmd_sync.file_checksum", lambda _path: "abc123")
    monkeypatch.setattr("wks.api.monitor.cmd_sync._enforce_monitor_db_limit", lambda *args, **kwargs: None)

    result = cmd_sync.cmd_sync(path=str(test_file), recursive=False)
    # File should be skipped because priority (0.3) < min_priority (0.5)
    assert result.output["files_synced"] == 0
    assert result.output["files_skipped"] == 1
    assert result.success is True
