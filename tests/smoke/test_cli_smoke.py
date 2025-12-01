"""CLI Smoke Tests.

These tests run the actual CLI commands against a temporary environment.
They ensure the end-to-end flow works as expected.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Path to the wks executable or module
WKS_CMD = [sys.executable, "-m", "wks.cli.main"]

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
        "db": {
            "type": "mongodb",
            "uri": "mongodb://localhost:27017"
        },
        "transform": {
            "cache_location": ".wks/cache"
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
    """Test 'wks config'."""
    result = run_wks(["config"], smoke_env)
    assert "Monitor" in result.stdout
    assert "Vault" in result.stdout

def test_cli_monitor_status(smoke_env):
    """Test 'wks monitor status'."""
    result = run_wks(["monitor", "status"], smoke_env)
    assert "Monitor Status" in result.stdout

def test_cli_vault_status(smoke_env):
    """Test 'wks vault status'."""
    result = run_wks(["vault", "status"], smoke_env)
    assert "Vault Status" in result.stdout

def test_cli_service_status(smoke_env):
    """Test 'wks service status'."""
    result = run_wks(["service", "status"], smoke_env)
    assert "Health" in result.stdout

# @pytest.mark.skip(reason="Transform command needs engine implementation")
def test_cli_transform(smoke_env):
    """Test 'wks transform'."""
    # Create a test file
    test_file = smoke_env["home"] / "test.txt"
    test_file.write_text("Hello World")
    
    # Run transform
    # Note: docling might not be installed, so this might fail if not mocked or handled.
    # But let's try.
    try:
        result = run_wks(["transform", "docling", str(test_file)], smoke_env)
    except subprocess.CalledProcessError as e:
        if "docling" in e.stderr.lower() or "not found" in e.stderr.lower():
             pytest.skip("docling not installed or failed")
        raise

    # Output should contain cache key (hex string)
    assert len(result.stdout.strip()) == 64
    
    # Check cache file exists
    cache_key = result.stdout.strip()
    cache_dir = smoke_env["home"] / ".wks" / "cache"
    assert (cache_dir / f"{cache_key}.md").exists()

# @pytest.mark.skip(reason="Cat command needs full implementation")
def test_cli_cat(smoke_env):
    """Test 'wks cat'."""
    test_file = smoke_env["home"] / "test.txt"
    test_file.write_text("Hello World")
    
    # Run cat with file path
    # This might fail if transform fails (due to docling)
    try:
        result = run_wks(["cat", str(test_file)], smoke_env)
        assert "Hello World" in result.stdout
    except subprocess.CalledProcessError as e:
        if "docling" in e.stderr.lower() or "not found" in e.stderr.lower():
             pytest.skip("docling not installed or failed")
        raise

# @pytest.mark.skip(reason="Diff engine 'unified' not implemented")
def test_cli_diff(smoke_env):
    """Test 'wks diff'."""
    file1 = smoke_env["home"] / "file1.txt"
    file1.write_text("Hello")
    file2 = smoke_env["home"] / "file2.txt"
    file2.write_text("World")
    
    result = run_wks(["diff", "unified", str(file1), str(file2)], smoke_env)
    assert "---" in result.stdout
    assert "+++" in result.stdout
