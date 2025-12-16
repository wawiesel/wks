"""Shared pytest configuration and fixtures for all tests."""

import json
import os
import platform
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
        "service": service_config_dict_for_platform(),
        "daemon": {
            "sync_interval_secs": 0.1,
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
