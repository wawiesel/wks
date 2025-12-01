"""CLI Smoke Tests.

These tests run the actual CLI commands against a temporary environment.
They ensure the end-to-end flow works as expected.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Path to the wks executable or module
WKS_CMD = [sys.executable, "-m", "wks.cli"]


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
    # Create config
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
            "prune_interval_secs": 3600
        },
        "vault": {
            "base_dir": str(home_dir / "Vault"),
            "database": "wks.vault",
            "wks_dir": "WKS"
        },
        "mongo": {
            "uri": "mongodb://localhost:27017"
        },
        "transform": {
            "cache": {
                "location": str(home_dir / ".wks" / "cache"),
                "max_size_bytes": 1073741824
            },
            "default_engine": "test",
            "database": "wks_transform"
        }
    }
    (home_dir / ".wks" / "config.json").write_text(json.dumps(config))

    # Add project root to PYTHONPATH
    project_root = str(Path(__file__).parents[2])
    env["PYTHONPATH"] = project_root

    return {"home": home_dir, "vault": vault_dir, "env": env}


def run_wks(args, env_dict, check=True):
    """Run WKS CLI command."""
    cmd = WKS_CMD + args
    result = subprocess.run(
        cmd,
        env=env_dict["env"],
        capture_output=True,
        text=True
    )
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


def test_cli_config_show(smoke_env):
    """Test 'wksc config' - outputs JSON with config keys."""
    result = run_wks(["config"], smoke_env)
    # Output contains JSON with vault key
    assert "vault" in result.stdout


def test_cli_monitor_status(smoke_env):
    """Test 'wksc monitor status' - outputs JSON with tracked_files."""
    result = run_wks(["monitor", "status"], smoke_env)
    assert "tracked_files" in result.stdout


def test_cli_vault_status(smoke_env):
    """Test 'wksc vault status' - outputs JSON with total_links."""
    result = run_wks(["vault", "status"], smoke_env)
    assert "total_links" in result.stdout


def test_cli_transform(smoke_env):
    """Test 'wksc transform' - outputs checksum."""
    test_file = smoke_env["home"] / "test.txt"
    test_file.write_text("Hello World")

    result = run_wks(["transform", "test", str(test_file)], smoke_env)

    # Output should contain cache key (64 char hex string)
    cache_key = result.stdout.strip()
    assert len(cache_key) == 64
    assert cache_key.isalnum()


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


def test_cli_diff(smoke_env):
    """Test 'wksc diff' - outputs diff."""
    file1 = smoke_env["home"] / "file1.txt"
    file1.write_text("Hello")
    file2 = smoke_env["home"] / "file2.txt"
    file2.write_text("World")

    result = run_wks(["diff", "unified", str(file1), str(file2)], smoke_env)
    assert "---" in result.stdout
    assert "+++" in result.stdout
