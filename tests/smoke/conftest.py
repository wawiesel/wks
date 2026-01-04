import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import check_mongod_available, get_mongo_connection_info, minimal_config_dict
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database


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


@pytest.fixture(scope="module")
def smoke_env(tmp_path_factory):
    """Create a temporary environment for smoke tests with real MongoDB."""
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

    config_dict = minimal_config_dict()
    mongo_uri, _, _is_local = get_mongo_connection_info(home_dir)

    # CRITICAL: RESPECT THE CONFIG
    config_dict["database"]["type"] = "mongo"
    config_dict["database"]["prefix"] = "wks_smoke"
    config_dict["database"]["data"] = {
        "uri": mongo_uri,
        "local": True,
    }
    config_dict["vault"] = {
        "type": "obsidian",
        "base_dir": str(vault_dir),
    }

    # Monitor configuration
    cache_dir = home_dir / "transform_cache"
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"] = [str(home_dir), str(cache_dir)]

    # Write config
    (wks_home / "config.json").write_text(json.dumps(config_dict), encoding="utf-8")

    # Start mongod via Database context manager
    os.environ["WKS_HOME"] = str(wks_home)
    config = WKSConfig.model_validate(config_dict)

    with Database(config.database, "setup") as db:
        db.get_client().server_info()
        yield {"home": home_dir, "vault": vault_dir, "env": env, "wksc_path": _find_wksc_command()}

    del os.environ["WKS_HOME"]


@pytest.fixture
def wksc(smoke_env):
    """Fixture to run wksc commands."""

    def run(args, check=True):
        cmd = [smoke_env["wksc_path"], *args]
        result = subprocess.run(cmd, env=smoke_env["env"], capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"Command failed: {' '.join(cmd)}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result

    return run
