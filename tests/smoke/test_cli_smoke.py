"""CLI Smoke Tests.

These tests verify that the installed `wksc` command works as a user would use it.
They test the CLI directly (not through MCP) to ensure installation is correct.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _mongo_available():
    """Check if MongoDB is available."""
    try:
        from pymongo import MongoClient

        client: MongoClient = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        client.server_info()
        client.close()
        return True
    except Exception:
        return False


def _find_wksc_command():
    """Find the installed wksc command.

    Prefers venv/bin/wksc if available, otherwise searches PATH.
    """
    # Check for venv in project root
    project_root = Path(__file__).parents[2]
    venv_wksc = project_root / ".venv" / "bin" / "wksc"
    if venv_wksc.exists():
        return str(venv_wksc)

    # Fall back to system PATH
    wksc_path = shutil.which("wksc")
    if wksc_path:
        return wksc_path

    # If not found, raise error with helpful message
    raise RuntimeError("wksc command not found. Please install the package: pip install -e .")


def _get_wks_cmd():
    """Get the wksc command path (lazy evaluation)."""
    return [_find_wksc_command()]


@pytest.fixture(scope="module")
def smoke_env(tmp_path_factory):
    """Create a temporary environment for smoke tests."""
    env_dir = tmp_path_factory.mktemp("smoke_env")
    home_dir = env_dir / "home"
    home_dir.mkdir()

    # Set HOME to the temp dir to isolate config
    env = os.environ.copy()
    env["HOME"] = str(home_dir)

    # Create a dummy vault
    vault_dir = home_dir / "Vault"
    vault_dir.mkdir()
    # Create config in current WKSConfig / DiffConfig format
    (home_dir / ".wks").mkdir()
    config = {
        "monitor": {
            "filter": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {"~": 100.0},
                "weights": {
                    "depth_multiplier": 0.9,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            "database": "monitor",
            "sync": {
                "max_documents": 10000,
                "min_priority": 0.0,
                "prune_interval_secs": 3600.0,
            },
        },
        "database": {
            "type": "mongo",
            "prefix": "wks",
            "data": {"uri": "mongodb://localhost:27017"},
        },
        "daemon": {
            "type": "darwin",
            "sync_interval_secs": 60.0,
            "data": {
                "label": "com.wks.daemon",
                "log_file": "daemon.log",
                "keep_alive": True,
                "run_at_load": False,
            },
        },
    }
    (home_dir / ".wks" / "config.json").write_text(json.dumps(config))

    # Don't add PYTHONPATH - we're testing the installed package, not the source
    # The installed wksc should work without PYTHONPATH manipulation

    return {"home": home_dir, "vault": vault_dir, "env": env}


def run_wks(args, env_dict, check=True):
    """Run WKS CLI command using the installed wksc binary."""
    cmd = _get_wks_cmd() + args
    result = subprocess.run(cmd, env=env_dict["env"], capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


def test_cli_config_show(smoke_env):
    """Test 'wksc config show' - outputs JSON with config keys."""
    result = run_wks(["config", "show", "monitor"], smoke_env)
    # Output contains JSON with monitor key (or content of monitor section)
    assert "priority" in result.stdout


def test_cli_config_list(smoke_env):
    """Test 'wksc config list' lists available sections."""
    result = run_wks(["config", "list"], smoke_env)
    assert "monitor" in result.stdout
    assert "database" in result.stdout


@pytest.mark.skipif(not _mongo_available(), reason="MongoDB not available")
def test_cli_monitor_status(smoke_env):
    """Test 'wksc monitor status' - outputs JSON with tracked_files."""
    result = run_wks(["monitor", "status"], smoke_env)
    assert "tracked_files" in result.stdout


def test_cli_mcp_list(smoke_env):
    """Test 'wksc mcp list' shows MCP installation info."""
    result = run_wks(["mcp", "list"], smoke_env)
    assert "installations" in result.stdout
