"""Shared pytest configuration and fixtures for all tests."""

import json
import os
import platform
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path

import pytest

from wks.api.config.WKSConfig import WKSConfig


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
            "max_documents": 1000000,
            "min_priority": 0.0,
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "data": {},
        },
        "service": service_config_dict_for_platform(),
        "daemon": {
            "sync_interval_secs": 0.1,
        },
        "vault": {
            "type": "obsidian",
            "base_dir": "~/_vault",
            "database": "vault",
        },
    }


def minimal_wks_config() -> WKSConfig:
    """Build a WKSConfig from the minimal config dict."""
    return WKSConfig(**minimal_config_dict())


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(name="minimal_config_dict")
def minimal_config_dict_fixture() -> dict:
    """Pytest fixture returning a copy of the minimal config dict."""
    return minimal_config_dict().copy()


@pytest.fixture(name="minimal_wks_config")
def minimal_wks_config_fixture() -> WKSConfig:
    """Pytest fixture returning a WKSConfig built from the minimal config dict."""
    return minimal_wks_config()


@pytest.fixture
def wks_home(tmp_path: Path, monkeypatch, minimal_config_dict: dict) -> Path:
    """Set up WKS_HOME with a minimal config file.

    Returns:
        Path to the WKS home directory (tmp_path)
    """
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))
    return tmp_path


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
    config = minimal_config_dict.copy()
    config["monitor"] = minimal_config_dict["monitor"].copy()
    config["monitor"]["filter"] = minimal_config_dict["monitor"]["filter"].copy()
    config["monitor"]["filter"]["include_paths"] = [str(watch_dir)]

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
        Path to the WKS home directory (tmp_path)
    """
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_with_priority_dirs))
    return tmp_path


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

    # Each worker gets 10000 ports, use path hash and pid for uniqueness
    mongo_port = base_port + (worker_num * 10000) + (path_hash % 9000) + (pid % 100)

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
    config_dict = minimal_config_dict()
    config_dict["database"] = {
        "type": "mongo",
        "prefix": "wks_test",
        "data": {
            "uri": mongo_uri,
            "local": is_local,
        },
    }
    config_dict["monitor"]["filter"]["include_paths"] = [str(watch_dir)]
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
