"""Shared pytest configuration and fixtures for all tests."""

import copy
import json
import os
import platform
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path

import pytest

from wks.api.config.WKSConfig import WKSConfig

# =============================================================================
# Pytest tmpdir cleanup race condition fix
# =============================================================================
# When using --basetemp with rapid sequential runs (like mutmut), pytest's
# cleanup_dead_symlinks can race with the next run's startup, causing
# FileNotFoundError. We patch it to gracefully ignore missing directories.


def _safe_cleanup_dead_symlinks(root):
    """Patched cleanup that ignores missing directories."""
    try:
        # Import the original implementation

        for left_dir in root.iterdir():
            try:
                if left_dir.is_symlink() and not left_dir.resolve().exists():
                    left_dir.unlink()
            except OSError:
                pass
    except FileNotFoundError:
        pass
    except OSError:
        pass


# Apply the patch on module load
try:
    from _pytest import pathlib as pytest_pathlib
    from _pytest import tmpdir as pytest_tmpdir

    pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
    pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
except ImportError:
    pass


def pytest_collection_modifyitems(config, items):
    """Automatically apply markers based on test file location."""
    for item in items:
        path_str = str(item.fspath)
        if "/smoke/" in path_str:
            item.add_marker(pytest.mark.smoke)
        elif "/unit/" in path_str:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in path_str:
            item.add_marker(pytest.mark.integration)


# =============================================================================
# Configuration Helpers
# =============================================================================


def service_config_dict_for_platform() -> dict:
    """Build a service config dict for the current platform.

    We do NOT fallback to a test backend. Unsupported platforms should fail tests,
    forcing explicit handling and avoiding hidden defaults.
    """
    backend_type = platform.system().lower()
    if backend_type == "darwin":
        return {
            "type": "darwin",
            "data": {
                "label": "com.test.wks",
                "keep_alive": True,
                "run_at_load": False,
            },
        }
    if backend_type == "linux":
        return {
            "type": "linux",
            "data": {
                "unit_name": "wks-test.service",
                "enabled": False,
            },
        }
    raise RuntimeError(f"Unsupported platform for service tests: {backend_type!r}")


def minimal_config_dict() -> dict:
    """Minimal valid WKS configuration dict for testing.

    Uses the current platform to populate the service backend; fails if unsupported.
    """
    return {
        "monitor": {
            "filter": {
                "include_paths": ["/tmp/wks_test_transform"],
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
            "remote": {
                "mappings": [],
            },
            "max_documents": 1000000,
            "min_priority": 0.0,
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "prune_frequency_secs": 3600,
            "data": {},
        },
        "service": service_config_dict_for_platform(),
        "daemon": {
            "sync_interval_secs": 0.1,
        },
        "vault": {
            "type": "obsidian",
            "base_dir": "~/_vault",
        },
        "log": {
            "level": "INFO",
            "debug_retention_days": 0.5,
            "info_retention_days": 1.0,
            "warning_retention_days": 2.0,
            "error_retention_days": 7.0,
        },
        "transform": {
            "cache": {
                "base_dir": "/tmp/wks_test_transform",
                "max_size_bytes": 1073741824,
            },
            "engines": {
                "test": {
                    "type": "test",
                    "data": {},
                },
                # Add docling engine to satisfy strict optional rules
                # (though usually invoked by name, if default_engine uses it)
                "docling_test": {
                    "type": "docling",
                    "data": {
                        "ocr": False,
                        "ocr_languages": ["eng"],
                        "image_export_mode": "embedded",
                        "pipeline": "standard",
                        "timeout_secs": 30,
                        "to": "md",
                    },
                },
            },
        },
        "cat": {
            "default_engine": "test",
        },
    }


def minimal_wks_config() -> WKSConfig:
    """Build a WKSConfig from the minimal config dict."""
    return WKSConfig(**minimal_config_dict())


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(name="minimal_config_dict")
def minimal_config_dict_fixture(tmp_path: Path) -> dict:
    """Pytest fixture returning a copy of the minimal config dict with isolated paths."""
    config = copy.deepcopy(minimal_config_dict())

    # Isolate transform cache to valid tmp path
    cache_dir = str(tmp_path / "transform_cache")
    config["transform"]["cache"]["base_dir"] = cache_dir

    # NEW RULE: Cache directory must be monitored
    config["monitor"]["filter"]["include_paths"].append(cache_dir)

    return config


@pytest.fixture(name="minimal_wks_config")
def minimal_wks_config_fixture() -> WKSConfig:
    """Pytest fixture returning a WKSConfig built from the minimal config dict."""
    return minimal_wks_config()


@pytest.fixture
def wks_home(tmp_path: Path, monkeypatch, minimal_config_dict: dict) -> Path:
    """Set up WKS_HOME with a minimal config file.

    Returns:
        Path to the WKS home directory (tmp_path / "wks_home")
    """
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    config_path = home_dir / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))
    return home_dir


@pytest.fixture
def wks_env(tmp_path: Path, minimal_config_dict: dict) -> dict:
    """Create a WKS environment with config for CLI testing.

    Returns dict with:
        - env: Environment dict with WKS_HOME set
        - wks_home: Path to WKS home directory
        - watch_dir: Path to watched directory
    """
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)

    watch_dir = tmp_path / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    # Update config with watch_dir
    config = copy.deepcopy(minimal_config_dict)
    config["monitor"]["filter"]["include_paths"].append(str(watch_dir))

    # Write config file
    config_file = wks_home / "config.json"
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Return environment with WKS_HOME set
    env = os.environ.copy()
    env["WKS_HOME"] = str(wks_home)
    return {
        "env": env,
        "wks_home": wks_home,
        "watch_dir": watch_dir,
    }


@pytest.fixture
def config_with_mcp(minimal_config_dict: dict) -> dict:
    """Config dict with MCP section added."""
    config = minimal_config_dict.copy()
    config["mcp"] = {"installs": {}}
    return config


@pytest.fixture
def config_with_priority_dirs(minimal_config_dict: dict) -> dict:
    """Config dict with monitor priority directories configured."""
    config = minimal_config_dict.copy()
    config["monitor"] = minimal_config_dict["monitor"].copy()
    config["monitor"]["priority"] = minimal_config_dict["monitor"]["priority"].copy()
    config["monitor"]["priority"]["dirs"] = {"~": 100.0}
    return config


@pytest.fixture
def wks_home_with_priority(tmp_path: Path, monkeypatch, config_with_priority_dirs: dict) -> Path:
    """Set up WKS_HOME with config that includes monitor priority directories.

    Returns:
        Path to the WKS home directory (tmp_path / "wks_home")
    """
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    config_path = home_dir / "config.json"
    config_path.write_text(json.dumps(config_with_priority_dirs))
    return home_dir


# =============================================================================
# Test Helpers
# =============================================================================


def run_cmd(cmd_func, *args, **kwargs):
    """Execute a cmd function and return the result with progress_callback executed."""
    result = cmd_func(*args, **kwargs)
    list(result.progress_callback(result))
    return result


# =============================================================================
# MongoDB Test Helpers
# =============================================================================


def check_mongod_available() -> bool:
    """Check if mongod is available and can be started."""
    if os.environ.get("WKS_TEST_MONGO_URI"):
        return True
    if not shutil.which("mongod"):
        return False
    # Try to connect to default port or check if we can start one
    try:
        result = subprocess.run(
            ["mongod", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_mongo_connection_info(tmp_path: Path) -> tuple[str, int, bool]:
    """Get MongoDB connection info (uri, port, is_local).

    Generates a unique but deterministic port based on tmp_path if not using external URI.
    """
    import hashlib
    import socket

    external_uri = os.environ.get("WKS_TEST_MONGO_URI")
    if external_uri:
        # Default port 27017 is a placeholder if parsing fails, but URI takes precedence
        return external_uri, 27017, False

    # Get worker ID from pytest-xdist if available
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    worker_num = 0
    if worker_id.startswith("gw"):
        with suppress(ValueError):
            worker_num = int(worker_id[2:])

    # Use tmp_path to generate a unique but deterministic port per test
    path_hash = int(hashlib.md5(str(tmp_path).encode()).hexdigest()[:6], 16)
    pid = os.getpid()
    base_port = 27100

    # Ensure port stays within 1024-65535 range
    # With 12 workers, we use worker_num * 1000 roughly
    mongo_port = base_port + (worker_num * 1000) + (path_hash % 900) + (pid % 10)

    # Verify port is actually available (in case of rare collision)
    max_attempts = 50
    original_port = mongo_port
    for attempt in range(max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", mongo_port))
                break  # Port is available
            except OSError:
                # Port in use, try next one in sequence
                mongo_port = original_port + attempt
                if mongo_port > 27999:
                    mongo_port = base_port + (attempt % 900)
    else:
        raise RuntimeError(f"Could not find available port after {max_attempts} attempts")

    return f"mongodb://127.0.0.1:{mongo_port}", mongo_port, True


@pytest.fixture
def mongo_wks_env(tmp_path, monkeypatch):
    """Set up WKS environment with real MongoDB.

    Yields dict with:
        - wks_home: Path to WKS home
        - watch_dir: Path to watched directory
        - config: WKSConfig object
        - mongo_port: Port used for MongoDB
    """
    if not check_mongod_available():
        pytest.fail(
            "MongoDB tests require `mongod` in PATH. "
            "Install MongoDB so `mongod --version` works, or run without -m mongo."
        )

    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    mongo_uri, mongo_port, is_local = get_mongo_connection_info(tmp_path)

    # Start with minimal config and override for MongoDB
    config_dict = copy.deepcopy(minimal_config_dict())
    config_dict["database"]["type"] = "mongo"
    config_dict["database"]["prefix"] = "wks_test"
    config_dict["database"]["data"] = {
        "uri": mongo_uri,
        "local": is_local,
    }

    # Isolate cache and ensure it is monitored
    cache_dir = str(tmp_path / "transform_cache")
    config_dict["transform"]["cache"]["base_dir"] = cache_dir
    config_dict["monitor"]["filter"]["include_paths"] = [str(watch_dir), cache_dir]
    config_dict["daemon"]["sync_interval_secs"] = 0.1

    monkeypatch.setenv("WKS_HOME", str(wks_home))
    config = WKSConfig.model_validate(config_dict)
    config.save()

    # Start mongod once for the duration of the test
    from wks.api.database.Database import Database

    with Database(config.database, "setup") as db:
        # Verify connection
        db.get_client().server_info()

        yield {
            "wks_home": wks_home,
            "watch_dir": watch_dir,
            "config": config,
            "mongo_port": mongo_port,
        }

    # Helper cleanup
    from wks.api.daemon.Daemon import Daemon

    with suppress(Exception):
        Daemon().stop()


# =============================================================================
# Tracked Config Helpers (Moved from unit/conftest.py)
# =============================================================================


class TrackedConfig:
    """Wrapper around WKSConfig that tracks save() calls.

    Use this when you need to verify that a command calls save().
    Delegates attribute access to the underlying config.
    """

    def __init__(self, config: WKSConfig):
        object.__setattr__(self, "_config", config)
        object.__setattr__(self, "save_calls", 0)
        object.__setattr__(self, "errors", [])
        object.__setattr__(self, "warnings", [])

    def __getattr__(self, name: str):
        return getattr(self._config, name)

    def __setattr__(self, name: str, value):
        if name in ("_config", "save_calls", "errors", "warnings"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._config, name, value)

    def save(self) -> None:
        self.save_calls += 1


def create_tracked_wks_config(
    monkeypatch, monitor_config_data: dict | None = None, config_dict: dict | None = None
) -> TrackedConfig:
    """Patch WKSConfig.load to return a TrackedConfig instance.

    Args:
        monkeypatch: pytest monkeypatch fixture
        monitor_config_data: Optional dictionary to update monitor config with.
            Can include 'filter' dict to update filter settings.
        config_dict: Optional configuration dictionary to use. If None, uses default minimal_config_dict().

    Returns:
        TrackedConfig instance that tracks save() calls.
    """
    base_config = copy.deepcopy(config_dict or minimal_config_dict())

    if monitor_config_data:
        # Deep merge monitor config data
        if "filter" in monitor_config_data:
            base_config["monitor"]["filter"].update(monitor_config_data["filter"])
        for key, value in monitor_config_data.items():
            if key != "filter":
                base_config["monitor"][key] = value

    config = WKSConfig(**base_config)
    tracked = TrackedConfig(config)
    monkeypatch.setattr(WKSConfig, "load", lambda: tracked)
    return tracked


@pytest.fixture
def tracked_wks_config(monkeypatch, minimal_config_dict: dict) -> TrackedConfig:
    """Fixture that patches WKSConfig with default settings and returns TrackedConfig."""
    return create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)
