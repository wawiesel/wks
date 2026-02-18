"""Index status command tests."""

import json

import pytest

from tests.conftest import run_cmd
from wks.api.index.cmd import cmd as index_cmd
from wks.api.index.cmd_status import cmd_status


@pytest.fixture
def index_env(tmp_path, monkeypatch):
    """Set up isolated WKS environment with index config."""
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))

    config_dict["index"] = {
        "default_index": "main",
        "indexes": {
            "main": {"engine": "textpass"},
        },
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    return {"cache_dir": cache_dir, "tmp_path": tmp_path}


def test_status_empty(index_env):
    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["indexes"]["main"]["document_count"] == 0
    assert result.output["indexes"]["main"]["chunk_count"] == 0


def test_status_after_indexing(index_env):
    doc = index_env["tmp_path"] / "test.txt"
    doc.write_text("Hello world this is a test.\n")

    run_cmd(index_cmd, "main", str(doc))

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["indexes"]["main"]["document_count"] == 1
    assert result.output["indexes"]["main"]["chunk_count"] >= 1


def test_status_specific_index(index_env):
    result = run_cmd(cmd_status, "main")
    assert result.success is True
    assert "main" in result.output["indexes"]


def test_status_no_config(tmp_path, monkeypatch):
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    result = run_cmd(cmd_status)
    assert result.success is False
    assert "not configured" in result.result.lower()
