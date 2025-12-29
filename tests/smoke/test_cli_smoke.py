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

from tests.conftest import check_mongod_available


def _require_mongod() -> None:
    """Fail loudly if MongoDB requirements are not met."""
    if not check_mongod_available():
        pytest.fail("Smoke tests require `mongod` in PATH. Install MongoDB so `mongod --version` works.")


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
    _require_mongod()
    env_dir = tmp_path_factory.mktemp("smoke_env")
    home_dir = env_dir / "home"
    home_dir.mkdir()

    # Set HOME to the temp dir to isolate config
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["WKS_HOME"] = str(home_dir / ".wks")

    # Symlink .local from real HOME to temp HOME so pip install --user packages are visible
    real_home = Path(os.environ["HOME"])
    if (real_home / ".local").exists() and not (home_dir / ".local").exists():
        (home_dir / ".local").symlink_to(real_home / ".local")

    # Create a dummy vault
    vault_dir = home_dir / "Vault"
    vault_dir.mkdir()
    wks_home = home_dir / ".wks"
    wks_home.mkdir()

    # Build a valid config using shared helpers, then override DB to use local Mongo.
    from tests.conftest import get_mongo_connection_info, minimal_config_dict
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.database.Database import Database

    config_dict = minimal_config_dict()
    mongo_uri, _, _is_local = get_mongo_connection_info(home_dir)  # Use _is_local to avoid unused var lint

    # CRITICAL: RESPECT THE CONFIG
    # We use the real Database implementation driven by standard configuration.
    # Setting `local: True` tells the backend to manage a local mongod process.
    # We do NOT manually spawn mongod; we let the config drive the system behavior.
    config_dict["database"]["type"] = "mongo"
    config_dict["database"]["prefix"] = "wks_smoke"
    config_dict["database"]["data"] = {
        "uri": mongo_uri,
        "local": True,  # Force local to ensure backend starts it if needed
    }
    config_dict["vault"] = {
        "type": "obsidian",
        "base_dir": str(vault_dir),
    }

    # Write config
    (wks_home / "config.json").write_text(json.dumps(config_dict), encoding="utf-8")

    # Start mongod via Database context manager and keep it running for the session
    # We must patch WKS_HOME so Database finds the right db_path (in temp home)
    os.environ["WKS_HOME"] = str(wks_home)

    config = WKSConfig.model_validate(config_dict)

    # Use Database context manager to start mongod based on the config.
    # This provides a persistent database instance for all tests in this module.
    # DO NOT switch to mongomock; we need to verify real persistence and connection logic.
    with Database(config.database, "setup") as db:
        # Verify connection
        db.get_client().server_info()

        yield {"home": home_dir, "vault": vault_dir, "env": env}

    # Database.__exit__ will attempt to terminate mongod
    # Also clean up WKS_HOME env var
    del os.environ["WKS_HOME"]


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


def test_cli_monitor_status(smoke_env):
    """Test 'wksc monitor status' - outputs JSON with tracked_files."""
    result = run_wks(["monitor", "status"], smoke_env)
    assert "tracked_files" in result.stdout


def test_cli_mcp_list(smoke_env):
    """Test 'wksc mcp list' shows MCP installation info."""
    result = run_wks(["mcp", "list"], smoke_env)
    assert "installations" in result.stdout


def test_cli_vault_sync(smoke_env):
    """Test 'wksc vault sync'."""
    # Ensure vault has content (created in test_cli_vault_check or here)
    vault_dir = smoke_env["vault"]
    if not (vault_dir / "smoke_test.md").exists():
        (vault_dir / "smoke_test.md").write_text("# Smoke Test\n[[Link]]", encoding="utf-8")

    result = run_wks(["vault", "sync"], smoke_env)

    # Verify sync success output
    assert "notes_scanned" in result.stdout
    assert "links_written" in result.stdout
    assert "success" in result.stdout
