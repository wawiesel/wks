"""Unit tests for wks.api.daemon._sync_path_static."""

import json
from unittest.mock import MagicMock

from wks.api.daemon._sync_path_static import _sync_path_static


def test_sync_path_static_success(monkeypatch, tmp_path, minimal_config_dict):
    """Test sync_path_static calls monitor sync."""
    # Setup config
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    log_file = tmp_path / "daemon.log"
    test_path = tmp_path / "test_dir"
    test_path.mkdir()

    logs = []

    def log_fn(msg: str) -> None:
        logs.append(msg)

    _sync_path_static(test_path, log_file, log_fn)

    # Should complete without error - may have warnings if no nodes


def test_sync_path_static_handles_runtime_error(monkeypatch, tmp_path):
    """Test runtime error handling for missing mongod."""
    log_file = tmp_path / "daemon.log"
    test_path = tmp_path / "test_dir"
    test_path.mkdir()

    logs = []

    def log_fn(msg: str) -> None:
        logs.append(msg)

    # Mock cmd_sync to raise RuntimeError
    mock_result = MagicMock()
    mock_result.progress_callback.side_effect = RuntimeError("mongod binary not found")
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.cmd_sync",
        lambda p: mock_result,
    )

    _sync_path_static(test_path, log_file, log_fn)

    assert any("mongod binary" in log for log in logs)


def test_sync_path_static_handles_generic_runtime_error(monkeypatch, tmp_path):
    """Test generic runtime error handling."""
    log_file = tmp_path / "daemon.log"
    test_path = tmp_path / "test_dir"
    test_path.mkdir()

    logs = []

    def log_fn(msg: str) -> None:
        logs.append(msg)

    # Mock cmd_sync to raise generic RuntimeError
    mock_result = MagicMock()
    mock_result.progress_callback.side_effect = RuntimeError("Some other error")
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.cmd_sync",
        lambda p: mock_result,
    )

    _sync_path_static(test_path, log_file, log_fn)

    assert any("sync failed" in log for log in logs)
