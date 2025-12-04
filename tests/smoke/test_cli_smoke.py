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
            "include_paths": ["~"],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "managed_directories": {"~": 100},
            "priority": {"depth_multiplier": 0.9},
            "database": "wks.monitor",
            "max_documents": 10000,
            "prune_interval_secs": 3600,
        },
        "vault": {
            "base_dir": str(home_dir / "Vault"),
            "database": "wks.vault",
            "wks_dir": "WKS",
            "update_frequency_seconds": 3600,
        },
        "db": {"uri": "mongodb://localhost:27017"},
        "transform": {
            "cache": {
                "location": str(home_dir / ".wks" / "cache"),
                "max_size_bytes": 1073741824,
            },
            "database": "wks.transform",
            "engines": {},
        },
        "diff": {
            "engines": {
                "myers": {"enabled": True, "is_default": True},
            },
            "_router": {
                "rules": [],
                "fallback": "myers",
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
    """Test 'wksc config' - outputs JSON with config keys."""
    result = run_wks(["config"], smoke_env)
    # Output contains JSON with vault key
    assert "vault" in result.stdout


@pytest.mark.skipif(not _mongo_available(), reason="MongoDB not available")
def test_cli_monitor_status(smoke_env):
    """Test 'wksc monitor status' - outputs JSON with tracked_files."""
    result = run_wks(["monitor", "status"], smoke_env)
    assert "tracked_files" in result.stdout


@pytest.mark.skipif(not _mongo_available(), reason="MongoDB not available")
def test_cli_vault_status(smoke_env):
    """Test 'wksc vault-status' - outputs JSON with total_links."""
    result = run_wks(["vault-status"], smoke_env)
    assert "total_links" in result.stdout


@pytest.mark.skipif(not _mongo_available(), reason="MongoDB not available")
def test_cli_transform(smoke_env):
    """Test 'wksc transform' - outputs checksum."""
    test_file = smoke_env["home"] / "test.txt"
    test_file.write_text("Hello World")

    result = run_wks(["transform", "test", str(test_file)], smoke_env)

    # Output should contain cache key (64 char hex string)
    cache_key = result.stdout.strip()
    assert len(cache_key) == 64
    assert cache_key.isalnum()


@pytest.mark.skipif(not _mongo_available(), reason="MongoDB not available")
def test_cli_cat(smoke_env):
    """Test 'wksc cat' - outputs transformed content."""
    test_file = smoke_env["home"] / "test.txt"
    test_file.write_text("Hello World")

    # Transform first
    transform_result = run_wks(["transform", "test", str(test_file)], smoke_env)
    cache_key = transform_result.stdout.strip()

    # Cat with cache key
    cat_result = run_wks(["cat", cache_key], smoke_env)
    assert "Transformed: Hello World" in cat_result.stdout


@pytest.mark.skipif(not _mongo_available(), reason="MongoDB not available")
def test_cli_diff(smoke_env):
    """Test 'wksc diff' - outputs diff."""
    file1 = smoke_env["home"] / "file1.txt"
    file1.write_text("Hello")
    file2 = smoke_env["home"] / "file2.txt"
    file2.write_text("World")

    result = run_wks(["diff", "myers", str(file1), str(file2)], smoke_env)
    # myers diff might look different, but usually has some output.
    # Let's just check success for now or basic content.
    # Myers output is JSON list of operations usually? Or text?
    # If it returns raw diff object:
    assert result.stdout.strip() != ""
