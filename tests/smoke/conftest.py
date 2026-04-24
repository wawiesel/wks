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
    if not check_mongod_available():
        pytest.fail("Smoke tests require `mongod` in PATH. Install MongoDB so `mongod --version` works.")


def _find_wksc_command():
    project_root = Path(__file__).parents[2]
    venv_wksc = project_root / "venv" / "bin" / "wksc"
    if venv_wksc.exists():
        return str(venv_wksc)

    wksc_path = shutil.which("wksc")
    if wksc_path:
        return wksc_path

    raise RuntimeError("wksc command not found. Please install the package: pip install -e .")


@pytest.fixture(scope="module")
def smoke_env(tmp_path_factory):
    _require_mongod()
    env_dir = tmp_path_factory.mktemp("smoke_env")
    home_dir = env_dir / "home"
    home_dir.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["WKS_HOME"] = str(home_dir / ".wks")

    real_home = Path(os.environ["HOME"])
    if (real_home / ".local").exists() and not (home_dir / ".local").exists():
        (home_dir / ".local").symlink_to(real_home / ".local")

    vault_dir = home_dir / "Vault"
    vault_dir.mkdir()
    wks_home = home_dir / ".wks"
    wks_home.mkdir()

    config_dict = minimal_config_dict()
    mongo_uri, _, _is_local = get_mongo_connection_info(home_dir)

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

    cache_dir = home_dir / "transform_cache"
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"] = [str(home_dir), str(cache_dir)]

    (wks_home / "config.json").write_text(json.dumps(config_dict), encoding="utf-8")

    os.environ["WKS_HOME"] = str(wks_home)
    config = WKSConfig.model_validate(config_dict)

    with Database(config.database, "setup") as db:
        db.get_client().server_info()
        yield {"home": home_dir, "vault": vault_dir, "env": env, "wksc_path": _find_wksc_command()}

    del os.environ["WKS_HOME"]


@pytest.fixture
def wksc(smoke_env):
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
