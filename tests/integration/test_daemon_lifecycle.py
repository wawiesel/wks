"""Tests for daemon lifecycle operations - initialization, start/stop/restart, lock management."""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import shared fixtures
from tests.integration.conftest import FakeCollection, FakeIndexer, FakeObserver, FakeVault
from wks.config import (
    DisplayConfig,
    MetricsConfig,
    MongoSettings,
    MonitorConfig,
    TransformConfig,
    VaultConfig,
    WKSConfig,
)
from wks.daemon import HealthData, WKSDaemon
from wks.monitor_rules import MonitorRules


def build_daemon_config(tmp_path):
    """Build a test WKSConfig."""
    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "include_paths": [str(tmp_path)],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {str(tmp_path): 100},
                "touch_weight": 0.5,
                "database": "wks.monitor",
                "max_documents": 1000000,
                "priority": {},
                "prune_interval_secs": 300.0,
            }
        }
    )
    vault_cfg = VaultConfig(
        base_dir=str(tmp_path),
        wks_dir="WKS",
        update_frequency_seconds=10,
        database="wks.vault",
        vault_type="obsidian",
    )
    mongo_cfg = MongoSettings(uri="mongodb://localhost:27017/")
    display_cfg = DisplayConfig()
    from wks.transform.config import CacheConfig

    transform_cfg = TransformConfig(
        cache=CacheConfig(location=Path(".wks/cache"), max_size_bytes=1024 * 1024 * 100),
        engines={},
        database="wks.transform",
    )
    metrics_cfg = MetricsConfig()

    return WKSConfig(
        monitor=monitor_cfg,
        vault=vault_cfg,
        mongo=mongo_cfg,
        display=display_cfg,
        transform=transform_cfg,
        metrics=metrics_cfg,
    )


def build_daemon(monkeypatch, tmp_path, collection=None, **daemon_kwargs):
    """Build a test daemon instance with mocked dependencies."""
    from wks import daemon as daemon_mod

    if collection is None:
        collection = FakeCollection()

    # Mock vault and indexer
    monkeypatch.setattr(daemon_mod, "ObsidianVault", FakeVault)
    monkeypatch.setattr(daemon_mod, "VaultLinkIndexer", FakeIndexer)

    # Mock MongoGuard
    class MockMongoGuard:
        def __init__(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(daemon_mod, "MongoGuard", MockMongoGuard)

    # Mock ensure_mongo_running
    monkeypatch.setattr(daemon_mod, "ensure_mongo_running", lambda *_a, **_k: None)

    # Mock MCPBroker
    mock_broker = MagicMock()
    mock_broker.start = MagicMock()
    mock_broker.stop = MagicMock()
    monkeypatch.setattr(daemon_mod, "MCPBroker", lambda *_a, **_k: mock_broker)

    # Mock start_monitoring
    mock_observer = FakeObserver()
    monkeypatch.setattr(daemon_mod, "start_monitoring", lambda *a, **k: mock_observer)  # noqa: ARG005

    # Mock db_activity functions
    monkeypatch.setattr(daemon_mod, "load_db_activity_summary", lambda: None)
    monkeypatch.setattr(daemon_mod, "load_db_activity_history", lambda *a: [])  # noqa: ARG005

    config = build_daemon_config(tmp_path)
    monitor_rules = MonitorRules.from_config(config.monitor)

    daemon = WKSDaemon(
        config=config,
        vault_path=tmp_path,
        base_dir="WKS",
        monitor_paths=[tmp_path],
        monitor_rules=monitor_rules,
        monitor_collection=collection,
        **daemon_kwargs,
    )

    return daemon


@pytest.mark.integration
class TestDaemonInitialization:
    """Test daemon initialization with various configs."""

    def test_daemon_init_basic(self, monkeypatch, tmp_path):
        """Test basic daemon initialization."""
        daemon = build_daemon(monkeypatch, tmp_path)

        assert daemon.config is not None
        assert daemon.vault is not None
        assert daemon.monitor_paths == [tmp_path]
        assert daemon.observer is None
        assert daemon._pending_deletes == {}
        assert daemon._pending_mods == {}

    def test_daemon_init_with_collection(self, monkeypatch, tmp_path):
        """Test daemon initialization with monitor collection."""
        collection = FakeCollection()
        daemon = build_daemon(monkeypatch, tmp_path, collection)

        assert daemon.monitor_collection == collection

    def test_daemon_init_without_mongo_uri(self, monkeypatch, tmp_path):
        """Test daemon initialization without MongoDB URI."""
        config = build_daemon_config(tmp_path)
        config.mongo.uri = None

        from wks import daemon as daemon_mod

        monkeypatch.setattr(daemon_mod, "ObsidianVault", FakeVault)
        monkeypatch.setattr(daemon_mod, "VaultLinkIndexer", FakeIndexer)

        monitor_rules = MonitorRules.from_config(config.monitor)
        daemon = WKSDaemon(
            config=config,
            vault_path=tmp_path,
            base_dir="WKS",
            monitor_paths=[tmp_path],
            monitor_rules=monitor_rules,
        )

        assert daemon.mongo_uri is None

    def test_daemon_init_rate_windows(self, monkeypatch, tmp_path):
        """Test daemon initialization with custom rate windows."""
        daemon = build_daemon(
            monkeypatch,
            tmp_path,
            fs_rate_short_window_secs=5.0,
            fs_rate_long_window_secs=300.0,
            fs_rate_short_weight=0.9,
            fs_rate_long_weight=0.1,
        )

        assert daemon.fs_rate_short_window == 5.0
        assert daemon.fs_rate_long_window == 300.0
        assert daemon.fs_rate_short_weight == 0.9
        assert daemon.fs_rate_long_weight == 0.1


@pytest.mark.integration
class TestDaemonStartStop:
    """Test daemon start/stop/restart scenarios."""

    def test_daemon_start(self, monkeypatch, tmp_path):
        """Test daemon start."""
        daemon = build_daemon(monkeypatch, tmp_path)

        # Mock lock acquisition
        with (
            patch.object(daemon, "_acquire_lock"),
            patch.object(daemon.vault, "ensure_structure"),
            patch.object(daemon, "_install_vault_git_hooks"),
        ):
            daemon.start()

        assert daemon.observer is not None

    def test_daemon_stop(self, monkeypatch, tmp_path):
        """Test daemon stop."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.observer = FakeObserver()

        with patch.object(daemon, "_release_lock"):
            daemon.stop()

        # Observer should be stopped (mocked)

    def test_daemon_stop_without_observer(self, monkeypatch, tmp_path):
        """Test daemon stop when observer is None."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.observer = None

        with patch.object(daemon, "_release_lock"):
            daemon.stop()

        # Should not raise exception

    def test_daemon_restart(self, monkeypatch, tmp_path):
        """Test daemon restart (stop then start)."""
        daemon = build_daemon(monkeypatch, tmp_path)

        with (
            patch.object(daemon, "_acquire_lock"),
            patch.object(daemon, "_release_lock"),
            patch.object(daemon.vault, "ensure_structure"),
            patch.object(daemon, "_install_vault_git_hooks"),
        ):
            daemon.start()
            daemon.stop()
            daemon.start()


@pytest.mark.integration
class TestDaemonLockManagement:
    """Test lock file management."""

    def test_lock_file_path(self, monkeypatch, tmp_path):
        """Test lock file path is set correctly."""
        daemon = build_daemon(monkeypatch, tmp_path)

        expected_path = Path.home() / ".wks" / "daemon.lock"
        assert daemon.lock_file == expected_path

    @patch("wks.daemon.fcntl", None)
    def test_acquire_lock_pidfile_fallback(self, monkeypatch, tmp_path):
        """Test lock acquisition using PID file when fcntl unavailable."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.lock_file = tmp_path / "test.lock"

        # Clean up stale lock
        with (
            patch.object(daemon, "_clean_stale_lock"),
            patch.object(daemon, "_pid_running", return_value=False),
        ):
            daemon._acquire_lock()

        # Lock file should exist
        assert daemon.lock_file.exists()

    def test_release_lock(self, monkeypatch, tmp_path):
        """Test lock release."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.lock_file = tmp_path / "test.lock"
        daemon.lock_file.write_text("12345")

        daemon._release_lock()

        # Lock file should be removed
        assert not daemon.lock_file.exists()

    def test_release_lock_with_file_handle(self, monkeypatch, tmp_path):
        """Test lock release with file handle."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.lock_file = tmp_path / "test.lock"
        mock_fh = MagicMock()
        daemon._lock_fh = mock_fh

        with patch("wks.daemon.fcntl") as mock_fcntl:
            daemon._release_lock()
            mock_fcntl.flock.assert_called_once()

    def test_clean_stale_lock(self, monkeypatch, tmp_path):
        """Test cleaning stale lock file."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.lock_file = tmp_path / "test.lock"
        daemon.lock_file.write_text("99999")  # Non-existent PID

        with patch.object(daemon, "_pid_running", return_value=False):
            daemon._clean_stale_lock()

        # Stale lock should be removed
        assert not daemon.lock_file.exists()

    def test_clean_stale_lock_running_process(self, monkeypatch, tmp_path):
        """Test that lock is not cleaned if process is running."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.lock_file = tmp_path / "test.lock"
        daemon.lock_file.write_text(str(os.getpid()))

        with patch.object(daemon, "_pid_running", return_value=True):
            daemon._clean_stale_lock()

        # Lock should still exist
        assert daemon.lock_file.exists()


@pytest.mark.integration
class TestDaemonHealthData:
    """Test health data collection and serialization."""

    def test_health_data_to_dict(self):
        """Test HealthData serialization to dict."""
        health = HealthData(
            pending_deletes=5,
            pending_mods=3,
            last_error="test error",
            pid=12345,
            last_error_at=1234567890,
            last_error_at_iso="2023-10-20 12:00:00",
            last_error_age_secs=60,
            started_at=1234567800,
            started_at_iso="2023-10-20 11:59:00",
            uptime_secs=90,
            uptime_hms="00:01:30",
            beats=100,
            avg_beats_per_min=1.5,
            lock_present=True,
            lock_pid=12345,
            lock_path="/path/to/lock",
            db_last_operation="update",
            db_last_operation_detail="test detail",
            db_last_operation_iso="2023-10-20 12:00:00",
            db_ops_last_minute=10,
            fs_rate_short=5.0,
            fs_rate_long=2.0,
            fs_rate_weighted=4.0,
            fs_rate_short_window_secs=10.0,
            fs_rate_long_window_secs=600.0,
            fs_rate_short_weight=0.8,
            fs_rate_long_weight=0.2,
        )

        data = health.to_dict()
        assert isinstance(data, dict)
        assert data["pending_deletes"] == 5
        assert data["pid"] == 12345
        assert data["uptime_secs"] == 90

    def test_write_health_file(self, monkeypatch, tmp_path):
        """Test writing health data to file."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.health_file = tmp_path / "health.json"
        daemon._health_started_at = time.time() - 100

        with (
            patch.object(daemon, "_get_db_activity_info", return_value=(None, None, None, 0)),
            patch.object(daemon, "_calculate_fs_rates", return_value=(0.0, 0.0, 0.0)),
            patch.object(daemon, "_get_lock_info", return_value=(False, None, str(daemon.lock_file))),
        ):
            daemon._write_health()

        assert daemon.health_file.exists()
        data = json.loads(daemon.health_file.read_text())
        assert "pid" in data
        assert "uptime_secs" in data
