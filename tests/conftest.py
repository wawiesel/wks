import copy
import json
import os
import platform
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from wks.api.config.WKSConfig import WKSConfig


def _safe_cleanup_dead_symlinks(root):
    try:
        for left_dir in root.iterdir():
            try:
                if left_dir.is_symlink() and not left_dir.resolve().exists():
                    left_dir.unlink()
            except OSError:
                pass
    except FileNotFoundError:
        pass
    except OSError:
        pass


try:
    from _pytest import pathlib as pytest_pathlib
    from _pytest import tmpdir as pytest_tmpdir

    pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
    pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
except ImportError:
    pass


def pytest_collection_modifyitems(config, items):
    for item in items:
        path_str = str(item.fspath)
        if "/smoke/" in path_str:
            item.add_marker(pytest.mark.smoke)
        elif "/unit/" in path_str:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in path_str:
            item.add_marker(pytest.mark.integration)


def service_config_dict_for_platform() -> dict:
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
    return {
        "monitor": {
            "filter": {
                "include_paths": ["/tmp/wks_test_transform"],
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
            "remote": {
                "mappings": [],
            },
            "max_documents": 1000000,
            "min_priority": 0.0,
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "prune_frequency_secs": 3600,
            "data": {},
        },
        "service": service_config_dict_for_platform(),
        "daemon": {
            "sync_interval_secs": 0.1,
        },
        "vault": {
            "type": "obsidian",
            "base_dir": "~/_vault",
        },
        "log": {
            "level": "INFO",
            "debug_retention_days": 0.5,
            "info_retention_days": 1.0,
            "warning_retention_days": 2.0,
            "error_retention_days": 7.0,
        },
        "transform": {
            "cache": {
                "base_dir": "/tmp/wks_test_transform",
                "max_size_bytes": 1073741824,
            },
            "default_engine": "textpass",
            "engines": {
                "textpass": {
                    "type": "textpass",
                    "data": {},
                },
                "docling_test": {
                    "type": "docling",
                    "data": {
                        "ocr": False,
                        "ocr_languages": ["eng"],
                        "image_export_mode": "embedded",
                        "pipeline": "standard",
                        "timeout_secs": 30,
                        "to": "md",
                    },
                },
            },
        },
        "cat": {"default_engine": "textpass"},
    }


def minimal_wks_config() -> WKSConfig:
    return WKSConfig(**minimal_config_dict())


@pytest.fixture(name="minimal_config_dict")
def minimal_config_dict_fixture(tmp_path: Path) -> dict:
    config = copy.deepcopy(minimal_config_dict())

    cache_dir = str(tmp_path / "transform_cache")
    config["transform"]["cache"]["base_dir"] = cache_dir

    config["vault"]["base_dir"] = str(tmp_path / "vault")

    config["monitor"]["filter"]["include_paths"].append(cache_dir)

    return config


@pytest.fixture(name="minimal_wks_config")
def minimal_wks_config_fixture() -> WKSConfig:
    return minimal_wks_config()


@pytest.fixture
def isolated_wks_home(tmp_path: Path, monkeypatch) -> Path:
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    return home_dir


@pytest.fixture
def wks_home(tmp_path: Path, monkeypatch, minimal_config_dict: dict) -> Path:
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    config_path = home_dir / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))
    return home_dir


@pytest.fixture
def wks_env(tmp_path: Path, minimal_config_dict: dict) -> dict:
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)

    watch_dir = tmp_path / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    config = copy.deepcopy(minimal_config_dict)
    config["monitor"]["filter"]["include_paths"].append(str(watch_dir))

    config_file = wks_home / "config.json"
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env["WKS_HOME"] = str(wks_home)
    return {
        "env": env,
        "wks_home": wks_home,
        "watch_dir": watch_dir,
    }


@pytest.fixture
def config_with_mcp(minimal_config_dict: dict) -> dict:
    config = minimal_config_dict.copy()
    config["mcp"] = {"installs": {}}
    return config


@pytest.fixture
def config_with_priority_dirs(minimal_config_dict: dict) -> dict:
    config = minimal_config_dict.copy()
    config["monitor"] = minimal_config_dict["monitor"].copy()
    config["monitor"]["priority"] = minimal_config_dict["monitor"]["priority"].copy()
    config["monitor"]["priority"]["dirs"] = {"~": 100.0}
    return config


@pytest.fixture
def wks_home_with_priority(tmp_path: Path, monkeypatch, config_with_priority_dirs: dict) -> Path:
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    config_path = home_dir / "config.json"
    config_path.write_text(json.dumps(config_with_priority_dirs))
    return home_dir


def run_cmd(cmd_func, *args, **kwargs):
    result = cmd_func(*args, **kwargs)
    list(result.progress_callback(result))
    return result


def ensure_watch_dir(wks_home: Path) -> Path:
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)
    return watch_dir


def write_watched_file(wks_home: Path, *, name: str, content: str) -> Path:
    test_file = ensure_watch_dir(wks_home) / name
    test_file.write_text(content, encoding="utf-8")
    return test_file


def build_service_test_config(
    tmp_path: Path,
    *,
    service_type: str,
    service_data: dict[str, Any],
    database_overrides: dict[str, Any] | None = None,
    log_overrides: dict[str, Any] | None = None,
) -> WKSConfig:
    config_dict = copy.deepcopy(minimal_config_dict())
    cache_dir = tmp_path / "cache"
    config_dict["monitor"]["filter"]["include_paths"] = [str(cache_dir)]
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["service"] = {"type": service_type, "data": service_data}
    if database_overrides:
        config_dict["database"].update(copy.deepcopy(database_overrides))
    if log_overrides:
        config_dict["log"].update(copy.deepcopy(log_overrides))
    return WKSConfig.model_validate(config_dict)


def check_mongod_available() -> bool:
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
        )
        return result.returncode == 0
    except Exception:
        return False


def get_mongo_connection_info(tmp_path: Path) -> tuple[str, int, bool]:
    import hashlib
    import socket

    external_uri = os.environ.get("WKS_TEST_MONGO_URI")
    if external_uri:
        return external_uri, 27017, False

    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    worker_num = 0
    if worker_id.startswith("gw"):
        with suppress(ValueError):
            worker_num = int(worker_id[2:])

    path_hash = int(hashlib.md5(str(tmp_path).encode()).hexdigest()[:6], 16)
    pid = os.getpid()
    base_port = 27100

    mongo_port = base_port + (worker_num * 1000) + (path_hash % 900) + (pid % 10)

    max_attempts = 50
    original_port = mongo_port
    for attempt in range(max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", mongo_port))
                break  # Port is available
            except OSError:
                mongo_port = original_port + attempt
                if mongo_port > 27999:
                    mongo_port = base_port + (attempt % 900)
    else:
        raise RuntimeError(f"Could not find available port after {max_attempts} attempts")

    return f"mongodb://127.0.0.1:{mongo_port}", mongo_port, True


@pytest.fixture
def mongo_wks_env(tmp_path, monkeypatch):
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

    config_dict = copy.deepcopy(minimal_config_dict())
    config_dict["database"]["type"] = "mongo"
    config_dict["database"]["prefix"] = "wks_test"
    config_dict["database"]["data"] = {
        "uri": mongo_uri,
        "local": is_local,
    }

    cache_dir = str(tmp_path / "transform_cache")
    config_dict["transform"]["cache"]["base_dir"] = cache_dir
    config_dict["monitor"]["filter"]["include_paths"] = [str(watch_dir), cache_dir]
    config_dict["daemon"]["sync_interval_secs"] = 0.1

    monkeypatch.setenv("WKS_HOME", str(wks_home))
    config = WKSConfig.model_validate(config_dict)
    config.save()

    from wks.api.database.Database import Database

    with Database(config.database, "setup") as db:
        db.get_client().server_info()

        yield {
            "wks_home": wks_home,
            "watch_dir": watch_dir,
            "config": config,
            "mongo_port": mongo_port,
        }

    from wks.api.daemon.Daemon import Daemon

    with suppress(Exception):
        Daemon().stop()


class TrackedConfig:
    def __init__(self, config: WKSConfig):
        object.__setattr__(self, "_config", config)
        object.__setattr__(self, "save_calls", 0)
        object.__setattr__(self, "errors", [])
        object.__setattr__(self, "warnings", [])

    def __getattr__(self, name: str):
        return getattr(self._config, name)

    def __setattr__(self, name: str, value):
        if name in ("_config", "save_calls", "errors", "warnings"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._config, name, value)

    def save(self) -> None:
        self.save_calls += 1


def create_tracked_wks_config(
    monkeypatch, monitor_config_data: dict | None = None, config_dict: dict | None = None
) -> TrackedConfig:
    base_config = copy.deepcopy(config_dict or minimal_config_dict())

    if monitor_config_data:
        if "filter" in monitor_config_data:
            base_config["monitor"]["filter"].update(monitor_config_data["filter"])
        for key, value in monitor_config_data.items():
            if key != "filter":
                base_config["monitor"][key] = value

    config = WKSConfig(**base_config)
    tracked = TrackedConfig(config)
    monkeypatch.setattr(WKSConfig, "load", lambda: tracked)
    return tracked


@pytest.fixture
def tracked_wks_config(monkeypatch, minimal_config_dict: dict) -> TrackedConfig:
    return create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)
