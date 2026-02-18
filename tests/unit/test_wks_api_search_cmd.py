"""Search command tests.

Tests the public cmd(query, index, k) function which performs
BM25 search over a named index.
"""

import json

import pytest

from tests.conftest import run_cmd
from wks.api.index.cmd import cmd as index_cmd
from wks.api.search.cmd import cmd as search_cmd


@pytest.fixture
def search_env(tmp_path, monkeypatch):
    """Build an index with several documents for search testing."""
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

    # Create test documents
    doc1 = tmp_path / "fission.txt"
    doc1.write_text(
        "Nuclear fission products are generated during reactor operation.\n"
        "The fission yield depends on the fissile isotope and neutron energy.\n"
    )
    doc2 = tmp_path / "python.txt"
    doc2.write_text(
        "Python programming language is used for scientific computing.\n"
        "Libraries like numpy and scipy provide numerical methods.\n"
    )
    doc3 = tmp_path / "coolant.txt"
    doc3.write_text(
        "Reactor coolant systems maintain safe operating temperatures.\n"
        "The primary loop transfers heat from the reactor core.\n"
    )

    # Index all three
    for doc in [doc1, doc2, doc3]:
        result = run_cmd(index_cmd, "main", str(doc))
        assert result.success is True

    return {"docs": [doc1, doc2, doc3]}


def test_search_finds_relevant(search_env):
    result = run_cmd(search_cmd, "fission yield")
    assert result.success is True
    assert len(result.output["hits"]) > 0
    # First hit should be the fission document
    assert "fission" in result.output["hits"][0]["text"].lower()


def test_search_returns_scores(search_env):
    result = run_cmd(search_cmd, "reactor")
    assert result.success is True
    for hit in result.output["hits"]:
        assert hit["score"] > 0
        assert "uri" in hit
        assert "text" in hit


def test_search_respects_k(search_env):
    result = run_cmd(search_cmd, "the", k=1)
    assert result.success is True
    assert len(result.output["hits"]) == 1


def test_search_no_match(search_env):
    result = run_cmd(search_cmd, "xyzzyplugh")
    assert result.success is True
    assert len(result.output["hits"]) == 0


def test_search_empty_index(tmp_path, monkeypatch):
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["index"] = {
        "default_index": "main",
        "indexes": {"main": {"engine": "textpass"}},
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    result = run_cmd(search_cmd, "hello")
    assert result.success is False
    assert "empty" in result.output["errors"][0].lower()


def test_search_uses_default_index(search_env):
    result = run_cmd(search_cmd, "fission")
    assert result.success is True
    assert result.output["index_name"] == "main"


def test_search_no_config(tmp_path, monkeypatch):
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

    result = run_cmd(search_cmd, "anything")
    assert result.success is False
    assert "not configured" in result.result.lower()
