"""Shared test fixtures for unit tests."""

import platform

import pytest

from wks.api.database.DatabaseConfig import DatabaseConfig
from wks.api.service.ServiceConfig import ServiceConfig
from wks.api.daemon.DaemonConfig import DaemonConfig
from wks.api.config.WKSConfig import WKSConfig


def _service_config_dict_for_current_platform() -> dict:
    """Build a service config dict for the current platform.

    We do NOT fallback to a test backend. Unsupported platforms should fail tests,
    forcing explicit handling and avoiding hidden defaults.
    """
    backend_type = platform.system().lower()
    if backend_type == "darwin":
        return {
            "type": "darwin",
            "sync_interval_secs": 60.0,
            "data": {
                "label": "com.test.wks",
                "keep_alive": True,
                "run_at_load": False,
            },
        }
    raise RuntimeError(f"Unsupported platform for service tests: {backend_type!r}")


class DummyConfig:
    """Mock WKSConfig for testing."""

    def __init__(self, monitor=None, database=None, service=None, daemon=None):
        from wks.api.monitor.MonitorConfig import MonitorConfig
        from wks.api.database.DatabaseConfig import DatabaseConfig

        self.monitor = monitor or MonitorConfig(
            filter={
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            priority={
                "dirs": {},
                "weights": {
                    "depth_multiplier": 0.9,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            database="monitor",
            sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
        )
        self.database = database or DatabaseConfig(type="mongomock", prefix="wks", data={})
        self.service = service or ServiceConfig(**_service_config_dict_for_current_platform())
        self.daemon = daemon or DaemonConfig(sync_interval_secs=0.1)
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


def minimal_config_dict() -> dict:
    """Minimal valid WKS configuration dict for testing (callable helper).

    Uses the current platform to populate the service backend; fails if unsupported.
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
        "service": _service_config_dict_for_current_platform(),
        "daemon": {
            "sync_interval_secs": 0.1
        },
    }


@pytest.fixture(name="minimal_config_dict")
def minimal_config_dict_fixture():
    """Pytest fixture wrapper returning the minimal config dict."""
    return minimal_config_dict().copy()


def minimal_wks_config() -> WKSConfig:
    """Helper to build a WKSConfig from the minimal config dict."""
    return WKSConfig(**minimal_config_dict())


@pytest.fixture(name="minimal_wks_config")
def minimal_wks_config_fixture():
    """Pytest fixture returning a WKSConfig built from the minimal config dict."""
    return minimal_wks_config()


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


def create_patched_config(monkeypatch, monitor_config_data=None):
    """Patch WKSConfig.load to return a DummyConfig instance.

    Args:
        monkeypatch: pytest monkeypatch fixture
        monitor_config_data: Optional dictionary to update monitor config with.
    """
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.database.DatabaseConfig import DatabaseConfig

    base_monitor_config = {
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
        "sync": {"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    }

    if monitor_config_data:
        # Update nested filter dict if present, otherwise set directly
        if "filter" in monitor_config_data and "filter" in base_monitor_config:
            base_monitor_config["filter"].update(monitor_config_data["filter"])
            # Remove filter from data to avoid overwriting the updated dict
            monitor_config_data = monitor_config_data.copy()
            del monitor_config_data["filter"]
        base_monitor_config.update(monitor_config_data)

    config = DummyConfig(
        monitor=MonitorConfig.from_config_dict({"monitor": base_monitor_config}),
        database=DatabaseConfig(type="mongomock", prefix="wks", data={}),
    )
    monkeypatch.setattr(WKSConfig, "load", lambda: config)
    return config


@pytest.fixture
def patch_wks_config(monkeypatch):
    """Fixture that patches WKSConfig with default settings."""
    return create_patched_config(monkeypatch)
