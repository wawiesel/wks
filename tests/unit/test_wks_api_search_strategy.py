import pytest

from tests.conftest import run_cmd
from tests.unit._search_test_helpers import (
    SEARCH_DOCS,
    fake_embed_texts,
    setup_search_config,
    write_and_index_search_docs,
)
from wks.api.index.cmd import cmd as index_cmd
from wks.api.index.cmd_embed import cmd_embed
from wks.api.search._rrf import rrf_merge
from wks.api.search.cmd import cmd as search_cmd


@pytest.fixture
def search_env_strategy(tmp_path, monkeypatch):
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "default_strategy": "hybrid",
            "strategies": {
                "hybrid": {"indexes": ["main", "semantic"], "merge": "rrf"},
            },
            "indexes": {
                "main": {"engine": "textpass"},
                "semantic": {"engine": "textpass", "embedding_model": "test-model"},
            },
        },
    )
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    docs = write_and_index_search_docs(tmp_path)
    for name, _content in SEARCH_DOCS.items():
        doc = tmp_path / name
        result = run_cmd(index_cmd, "semantic", str(doc))
        assert result.success is True
    embed_res = run_cmd(cmd_embed, "semantic", batch_size=8)
    assert embed_res.success is True
    return {"docs": docs}


def test_strategy_search_combined(search_env_strategy):
    result = run_cmd(search_cmd, "fission", strategy="hybrid")
    assert result.success is True
    assert result.output["search_mode"] == "combined"
    assert result.output["index_name"] == "hybrid"
    assert result.output["embedding_model"] is None
    assert len(result.output["hits"]) > 0


def test_strategy_default_used(search_env_strategy):
    result = run_cmd(search_cmd, "fission")
    assert result.success is True
    assert result.output["search_mode"] == "combined"
    assert result.output["index_name"] == "hybrid"


def test_strategy_explicit_index_overrides_default_strategy(search_env_strategy):
    result = run_cmd(search_cmd, "fission", index="main")
    assert result.success is True
    assert result.output["search_mode"] == "lexical"
    assert result.output["index_name"] == "main"


def test_strategy_and_index_mutually_exclusive(search_env_strategy):
    result = run_cmd(search_cmd, "fission", index="main", strategy="hybrid")
    assert result.success is False
    assert "cannot specify both" in result.output["errors"][0].lower()


def test_strategy_unknown_name(search_env_strategy):
    result = run_cmd(search_cmd, "fission", strategy="nonexistent")
    assert result.success is False
    assert "not defined" in result.output["errors"][0].lower()


def test_rrf_merge_basic():
    list_a = [
        {"uri": "a.txt", "chunk_index": 0, "score": 1.0, "tokens": 10, "text": "a"},
        {"uri": "b.txt", "chunk_index": 0, "score": 0.5, "tokens": 10, "text": "b"},
    ]
    list_b = [
        {"uri": "b.txt", "chunk_index": 0, "score": 1.0, "tokens": 10, "text": "b"},
        {"uri": "c.txt", "chunk_index": 0, "score": 0.5, "tokens": 10, "text": "c"},
    ]
    merged = rrf_merge([list_a, list_b], k=3)
    assert merged[0]["uri"] == "b.txt"
    assert len(merged) == 3
