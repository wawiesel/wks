"""Shared test fixtures for unit tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from wks.api.database.DatabaseConfig import DatabaseConfig


class DummyConfig:
    """Mock WKSConfig for testing."""

    def __init__(self, monitor=None, database=None, daemon=None):
        from wks.api.monitor.MonitorConfig import MonitorConfig
        from wks.api.database.DatabaseConfig import DatabaseConfig

        self.monitor = monitor or MonitorConfig(
            filter={},
            priority={"dirs": {}, "weights": {}},
            database="monitor",
            sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
        )
        self.database = database or DatabaseConfig(type="mongomock", prefix="wks", data={})
        self.daemon = daemon
        self.save_calls = 0
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def save(self):
        self.save_calls += 1


@pytest.fixture
def mock_config():
    """Create a minimal mock WKSConfig."""
    return DummyConfig()


def run_cmd(cmd_func, *args, **kwargs):
    """Execute a cmd function and return the result with progress_callback executed."""
    result = cmd_func(*args, **kwargs)
    list(result.progress_callback(result))
    return result


@pytest.fixture
def minimal_config_dict():
    """Minimal valid WKS configuration dict for testing.

    This is the simplest valid config - all required fields with minimal values.
    Use this as a base and modify for specific test cases.
    """
    return {
        "monitor": {
            "filter": {
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {},
                "weights": {
                    "depth_multiplier": 0.9,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            "database": "monitor",
            "sync": {
                "max_documents": 1000000,
                "min_priority": 0.0,
                "prune_interval_secs": 300.0,
            },
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "data": {},
        },
        "daemon": {
            "type": "macos",
            "data": {
                "label": "com.test.wks",
                "log_file": "daemon.log",
                "error_log_file": "daemon.error.log",
                "keep_alive": True,
                "run_at_load": False,
            },
        },
    }


@pytest.fixture
def standard_config_dict(minimal_config_dict):
    """Standard valid WKS configuration dict for testing.

    Alias for minimal_config_dict - use minimal_config_dict directly.
    """
    return minimal_config_dict


@pytest.fixture
def config_with_mcp(minimal_config_dict):
    """Config dict with MCP section added."""
    minimal_config_dict["mcp"] = {
        "installs": {}
    }
    return minimal_config_dict


@pytest.fixture
def config_with_monitor_priority(minimal_config_dict):
    """Config dict with monitor priority directories configured."""
    minimal_config_dict["monitor"]["priority"]["dirs"] = {"~": 100.0}
    return minimal_config_dict


@pytest.fixture
def wks_home(tmp_path, monkeypatch, minimal_config_dict):
    """Set up WKS_HOME with a minimal config file.

    Returns:
        Path to the WKS home directory (tmp_path)
    """
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    # Write minimal config
    config_path = tmp_path / "config.json"
    import json
    config_path.write_text(json.dumps(minimal_config_dict))

    return tmp_path


@pytest.fixture
def wks_home_with_priority(tmp_path, monkeypatch, config_with_monitor_priority):
    """Set up WKS_HOME with config file that includes monitor priority directories.

    Returns:
        Path to the WKS home directory (tmp_path)
    """
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    # Write config with priority
    config_path = tmp_path / "config.json"
    import json
    config_path.write_text(json.dumps(config_with_monitor_priority))

    return tmp_path


@pytest.fixture
def patch_wks_config(monkeypatch):
    """Patch WKSConfig.load to return a DummyConfig instance."""
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.database.DatabaseConfig import DatabaseConfig

    config = DummyConfig(
        monitor=MonitorConfig(
            filter={},
            priority={"dirs": {}, "weights": {}},
            database="monitor",
            sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
        ),
        database=DatabaseConfig(type="mongomock", prefix="wks", data={}),
    )
    monkeypatch.setattr(WKSConfig, "load", lambda: config)
    return config
