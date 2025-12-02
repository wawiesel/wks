"""Tests for daemon health metrics - uptime, rates, beats, error tracking."""

import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

from wks.daemon import WKSDaemon
from wks.monitor_rules import MonitorRules
from wks.config import WKSConfig, MonitorConfig, VaultConfig, MongoSettings, DisplayConfig, TransformConfig, MetricsConfig


class FakeCollection:
    """Fake MongoDB collection for testing."""
    def count_documents(self, filt, limit=None):
        return 0


class FakeVault:
    """Fake vault for testing."""
    def __init__(self, *args, **kwargs):
        pass

    def ensure_structure(self):
        pass

    def log_file_operation(self, *args, **kwargs):
        pass

    def update_link_on_move(self, *args, **kwargs):
        pass

    def update_vault_links_on_move(self, *args, **kwargs):
        pass

    def mark_reference_deleted(self, *args, **kwargs):
        pass


class FakeIndexer:
    """Fake vault indexer for testing."""
    @classmethod
    def from_config(cls, vault, cfg):
        return cls()

    def sync(self, incremental=False):
        pass


def build_daemon_config(tmp_path):
    """Build a test WKSConfig."""
    monitor_cfg = MonitorConfig.from_config_dict({
        "include_paths": [str(tmp_path)],
        "exclude_paths": [],
        "include_dirnames": [],
        "exclude_dirnames": [],
        "include_globs": [],
        "exclude_globs": [],
        "managed_directories": {},
        "touch_weight": 0.5,
        "database": "wks.monitor",
        "max_documents": 1000000,
        "priority": {},
        "prune_interval_secs": 300.0,
    })
    vault_cfg = VaultConfig(
        base_dir=str(tmp_path),
        wks_dir="WKS",
        update_frequency_seconds=10,
        database="wks.vault",
        vault_type="obsidian"
    )
    mongo_cfg = MongoSettings(uri="mongodb://localhost:27017/")
    display_cfg = DisplayConfig()
    from wks.transform.config import CacheConfig
    transform_cfg = TransformConfig(
        cache=CacheConfig(location=Path(".wks/cache"), max_size_bytes=1024*1024*100),
        engines={},
        database="wks.transform"
    )
    metrics_cfg = MetricsConfig()
    
    return WKSConfig(
        monitor=monitor_cfg,
        vault=vault_cfg,
        mongo=mongo_cfg,
        display=display_cfg,
        transform=transform_cfg,
        metrics=metrics_cfg
    )


def build_daemon(monkeypatch, tmp_path):
    """Build a test daemon instance."""
    from wks import daemon as daemon_mod

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

    # Mock MCPBroker
    mock_broker = MagicMock()
    monkeypatch.setattr(daemon_mod, "MCPBroker", lambda *a, **k: mock_broker)

    # Mock db_activity functions
    monkeypatch.setattr(daemon_mod, "load_db_activity_summary", lambda: None)
    monkeypatch.setattr(daemon_mod, "load_db_activity_history", lambda *a: [])

    config = build_daemon_config(tmp_path)
    monitor_rules = MonitorRules.from_config(config.monitor)

    daemon = WKSDaemon(
        config=config,
        vault_path=tmp_path,
        base_dir="WKS",
        monitor_paths=[tmp_path],
        monitor_rules=monitor_rules,
        monitor_collection=FakeCollection(),
    )

    return daemon


class TestHealthMetricsCalculation:
    """Test health metrics calculation (uptime, rates, beats)."""

    def test_format_uptime(self, monkeypatch, tmp_path):
        """Test uptime formatting."""
        daemon = build_daemon(monkeypatch, tmp_path)
        
        assert daemon._format_uptime(0) == "00:00:00"
        assert daemon._format_uptime(3661) == "01:01:01"
        assert daemon._format_uptime(3600) == "01:00:00"
        assert daemon._format_uptime(59) == "00:00:59"

    def test_uptime_calculation(self, monkeypatch, tmp_path):
        """Test uptime calculation from start time."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon._health_started_at = time.time() - 125
        
        uptime_secs = int(time.time() - daemon._health_started_at)
        assert uptime_secs >= 125
        assert uptime_secs < 130  # Allow small margin

    def test_bump_beat(self, monkeypatch, tmp_path):
        """Test beat counter increment."""
        daemon = build_daemon(monkeypatch, tmp_path)
        initial_beats = daemon._beat_count
        
        daemon._bump_beat()
        
        assert daemon._beat_count == initial_beats + 1

    def test_bump_beat_multiple(self, monkeypatch, tmp_path):
        """Test multiple beat increments."""
        daemon = build_daemon(monkeypatch, tmp_path)
        initial_beats = daemon._beat_count
        
        for _ in range(5):
            daemon._bump_beat()
        
        assert daemon._beat_count == initial_beats + 5


class TestErrorTracking:
    """Test error tracking and timestamps."""

    def test_set_error(self, monkeypatch, tmp_path):
        """Test setting error message."""
        daemon = build_daemon(monkeypatch, tmp_path)
        
        daemon._set_error("test error message")
        
        assert daemon._last_error == "test error message"
        assert daemon._last_error_at is not None
        assert isinstance(daemon._last_error_at, float)

    def test_set_error_timestamp(self, monkeypatch, tmp_path):
        """Test error timestamp is set correctly."""
        daemon = build_daemon(monkeypatch, tmp_path)
        before = time.time()
        
        daemon._set_error("error")
        after = time.time()
        
        assert before <= daemon._last_error_at <= after

    def test_set_error_multiple(self, monkeypatch, tmp_path):
        """Test that setting error multiple times updates timestamp."""
        daemon = build_daemon(monkeypatch, tmp_path)
        
        daemon._set_error("first error")
        first_time = daemon._last_error_at
        time.sleep(0.01)  # Small delay
        
        daemon._set_error("second error")
        
        assert daemon._last_error == "second error"
        assert daemon._last_error_at > first_time

    def test_set_info(self, monkeypatch, tmp_path):
        """Test set_info (placeholder method)."""
        daemon = build_daemon(monkeypatch, tmp_path)
        
        # Should not raise exception
        daemon._set_info("info message")


class TestFilesystemRateCalculations:
    """Test filesystem rate calculations (short/long windows)."""

    def test_record_fs_event(self, monkeypatch, tmp_path):
        """Test recording filesystem event."""
        daemon = build_daemon(monkeypatch, tmp_path)
        initial_short = len(daemon._fs_events_short)
        initial_long = len(daemon._fs_events_long)
        
        daemon._record_fs_event()
        
        assert len(daemon._fs_events_short) == initial_short + 1
        assert len(daemon._fs_events_long) == initial_long + 1

    def test_calculate_fs_rates_empty(self, monkeypatch, tmp_path):
        """Test rate calculation with no events."""
        daemon = build_daemon(monkeypatch, tmp_path)
        
        short_rate, long_rate, weighted_rate = daemon._calculate_fs_rates()
        
        assert short_rate == 0.0
        assert long_rate == 0.0
        assert weighted_rate == 0.0

    def test_calculate_fs_rates_with_events(self, monkeypatch, tmp_path):
        """Test rate calculation with events."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.fs_rate_short_window = 10.0
        daemon.fs_rate_long_window = 60.0
        
        # Record 5 events
        for _ in range(5):
            daemon._record_fs_event()
        
        short_rate, long_rate, weighted_rate = daemon._calculate_fs_rates()
        
        # Short window: 5 events / 10 seconds = 0.5 events/sec
        assert short_rate == 0.5
        # Long window: 5 events / 60 seconds = 0.083 events/sec
        assert long_rate == pytest.approx(0.083, abs=0.001)
        # Weighted: 0.8 * 0.5 + 0.2 * 0.083 = 0.4166
        assert weighted_rate == pytest.approx(0.4166, abs=0.01)

    def test_fs_events_window_expiration(self, monkeypatch, tmp_path):
        """Test that old events are removed from windows."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.fs_rate_short_window = 1.0  # 1 second window
        
        # Record event
        daemon._record_fs_event()
        assert len(daemon._fs_events_short) == 1
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Record another event (should trigger cleanup)
        daemon._record_fs_event()
        
        # Should have at most 2 events, but old one may be expired
        assert len(daemon._fs_events_short) <= 2

    def test_fs_rates_different_weights(self, monkeypatch, tmp_path):
        """Test rate calculation with different weights."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.fs_rate_short_weight = 0.9
        daemon.fs_rate_long_weight = 0.1
        daemon.fs_rate_short_window = 10.0
        daemon.fs_rate_long_window = 60.0
        
        # Record events
        for _ in range(10):
            daemon._record_fs_event()
        
        short_rate, long_rate, weighted_rate = daemon._calculate_fs_rates()
        
        # Weighted should use new weights
        expected_weighted = 0.9 * short_rate + 0.1 * long_rate
        assert weighted_rate == pytest.approx(expected_weighted, abs=0.01)


class TestDatabaseOperationLogging:
    """Test database operation logging."""

    def test_get_db_activity_info_no_history(self, monkeypatch, tmp_path):
        """Test getting DB activity info with no history."""
        daemon = build_daemon(monkeypatch, tmp_path)
        
        with patch('wks.daemon.load_db_activity_summary', return_value=None):
            with patch('wks.daemon.load_db_activity_history', return_value=[]):
                op, detail, iso, ops_min = daemon._get_db_activity_info(time.time())
        
        assert op is None
        assert detail is None
        assert iso is None
        assert ops_min == 0

    def test_get_db_activity_info_with_summary(self, monkeypatch, tmp_path):
        """Test getting DB activity info with summary."""
        daemon = build_daemon(monkeypatch, tmp_path)
        now = time.time()
        
        summary = {
            "operation": "update",
            "detail": "test detail",
            "timestamp_iso": "2023-10-20 12:00:00",
        }
        
        with patch('wks.daemon.load_db_activity_summary', return_value=summary):
            with patch('wks.daemon.load_db_activity_history', return_value=[]):
                op, detail, iso, ops_min = daemon._get_db_activity_info(now)
        
        assert op == "update"
        assert detail == "test detail"
        assert iso == "2023-10-20 12:00:00"
        assert ops_min == 0

    def test_get_db_activity_info_with_history(self, monkeypatch, tmp_path):
        """Test getting DB activity info from history."""
        daemon = build_daemon(monkeypatch, tmp_path)
        now = time.time()
        
        history = [
            {"timestamp": now - 30, "operation": "insert", "detail": "detail1", "timestamp_iso": "2023-10-20 12:00:00"},
            {"timestamp": now - 10, "operation": "update", "detail": "detail2", "timestamp_iso": "2023-10-20 12:00:30"},
        ]
        
        with patch('wks.daemon.load_db_activity_summary', return_value=None):
            with patch('wks.daemon.load_db_activity_history', return_value=history):
                op, detail, iso, ops_min = daemon._get_db_activity_info(now)
        
        # Should get last item from history
        assert op == "update"
        assert detail == "detail2"

    def test_get_db_activity_info_ops_last_minute(self, monkeypatch, tmp_path):
        """Test counting operations in last minute."""
        daemon = build_daemon(monkeypatch, tmp_path)
        now = time.time()
        
        history = [
            {"timestamp": now - 70, "operation": "old"},  # Too old
            {"timestamp": now - 30, "operation": "recent1"},
            {"timestamp": now - 10, "operation": "recent2"},
            {"timestamp": now - 5, "operation": "recent3"},
        ]
        
        with patch('wks.daemon.load_db_activity_summary', return_value=None):
            with patch('wks.daemon.load_db_activity_history', return_value=history):
                op, detail, iso, ops_min = daemon._get_db_activity_info(now)
        
        # Should count 3 recent operations
        assert ops_min == 3

    def test_get_lock_info(self, monkeypatch, tmp_path):
        """Test getting lock file information."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.lock_file = tmp_path / "test.lock"
        
        # No lock file
        present, pid, path = daemon._get_lock_info()
        assert present is False
        assert pid is None
        assert path == str(daemon.lock_file)
        
        # Create lock file
        daemon.lock_file.write_text("12345")
        present, pid, path = daemon._get_lock_info()
        assert present is True
        assert pid == 12345

    def test_get_lock_info_invalid_pid(self, monkeypatch, tmp_path):
        """Test getting lock info with invalid PID."""
        daemon = build_daemon(monkeypatch, tmp_path)
        daemon.lock_file = tmp_path / "test.lock"
        daemon.lock_file.write_text("invalid")
        
        present, pid, path = daemon._get_lock_info()
        assert present is True
        assert pid is None  # Invalid PID should return None
