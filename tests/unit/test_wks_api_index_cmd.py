"""Index command tests.

Tests the public cmd(name, uri) function which transforms, chunks,
and stores a document in a named index.
"""

import json

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.index.cmd import cmd


def _make_index_env(tmp_path, monkeypatch, *, with_file=True):
    """Set up an index-ready WKS environment with transform cache and config."""
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
            "alt": {"engine": "textpass", "max_tokens": 128, "overlap_tokens": 32},
        },
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    test_file = None
    if with_file:
        test_file = tmp_path / "doc.txt"
        test_file.write_text("Nuclear fission products are generated during reactor operation.\n" * 20)

    return {"cache_dir": cache_dir, "test_file": test_file}


def test_cmd_index_success(tmp_path, monkeypatch):
    env = _make_index_env(tmp_path, monkeypatch)
    result = run_cmd(cmd, "main", str(env["test_file"]))
    assert result.success is True
    assert result.output["index_name"] == "main"
    assert result.output["chunk_count"] >= 1
    assert result.output["checksum"] != ""


def test_cmd_index_unknown_index(tmp_path, monkeypatch):
    env = _make_index_env(tmp_path, monkeypatch)
    result = run_cmd(cmd, "nonexistent", str(env["test_file"]))
    assert result.success is False
    assert "nonexistent" in result.output["errors"][0]


def test_cmd_index_no_config(tmp_path, monkeypatch):
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    # No index config

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    result = run_cmd(cmd, "main", "/tmp/whatever.txt")
    assert result.success is False
    assert "not configured" in result.result.lower()


def test_cmd_index_file_not_found(tmp_path, monkeypatch):
    _make_index_env(tmp_path, monkeypatch, with_file=False)
    result = run_cmd(cmd, "main", str(tmp_path / "missing.txt"))
    assert result.success is False
    assert "not found" in result.output["errors"][0].lower()


def test_cmd_index_alt_index(tmp_path, monkeypatch):
    env = _make_index_env(tmp_path, monkeypatch)
    result = run_cmd(cmd, "alt", str(env["test_file"]))
    assert result.success is True
    assert result.output["index_name"] == "alt"
    assert result.output["chunk_count"] >= 1


def test_cmd_index_with_file_uri(tmp_path, monkeypatch):
    """MCP passes file:// URI strings — cmd must resolve to filesystem path."""
    env = _make_index_env(tmp_path, monkeypatch)
    file_uri = str(URI.from_path(env["test_file"]))
    result = run_cmd(cmd, "main", file_uri)
    assert result.success is True
    assert result.output["chunk_count"] >= 1


def test_cmd_index_with_uri_object(tmp_path, monkeypatch):
    """MCP handler may pass a URI object directly."""
    env = _make_index_env(tmp_path, monkeypatch)
    uri_obj = URI.from_path(env["test_file"])
    result = run_cmd(cmd, "main", uri_obj)
    assert result.success is True
    assert result.output["chunk_count"] >= 1
