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


def _mongod_available() -> bool:
    """Return True only if the `mongod` binary is available."""
    if os.environ.get("WKS_TEST_MONGO_URI"):
        return True
    if not shutil.which("mongod"):
        return False
    try:
        result = subprocess.run(
            ["mongod", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _require_mongod() -> None:
    """Fail loudly if MongoDB requirements are not met."""
    if not _mongod_available():
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
    # Content of Dockerfile or local env might set WKS_HOME, so we must override it
    # to ensure the app looks in our temp dir, not the hardcoded /home/testuser/.wks
    env["WKS_HOME"] = str(home_dir / ".wks")

    # Symlink .local from real HOME to temp HOME so pip install --user packages are visible
    real_home = Path(os.environ["HOME"])
    if (real_home / ".local").exists():
        (home_dir / ".local").symlink_to(real_home / ".local")

    # Create a dummy vault
    vault_dir = home_dir / "Vault"
    vault_dir.mkdir()
    (home_dir / ".wks").mkdir()
    # Build a valid config using shared helpers, then override DB to use local Mongo.
    import random

    from tests.conftest import minimal_config_dict

    config = minimal_config_dict()

    mongo_port = 27017
    external_uri = os.environ.get("WKS_TEST_MONGO_URI")

    if external_uri:
        mongo_uri = external_uri
        is_local = False
    else:
        mongo_port = random.randint(27100, 27999)
        mongo_uri = f"mongodb://127.0.0.1:{mongo_port}"
        is_local = True

    config["database"] = {
        "type": "mongo",
        "prefix": "wks_smoke",
        "data": {
            "uri": mongo_uri,
            "local": is_local,
        },
    }

    (home_dir / ".wks" / "config.json").write_text(json.dumps(config), encoding="utf-8")

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


def test_cli_monitor_status(smoke_env):
    """Test 'wksc monitor status' - outputs JSON with tracked_files."""
    result = run_wks(["monitor", "status"], smoke_env)
    assert "tracked_files" in result.stdout


def test_cli_mcp_list(smoke_env):
    """Test 'wksc mcp list' shows MCP installation info."""
    result = run_wks(["mcp", "list"], smoke_env)
    assert "installations" in result.stdout
