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
from wks.api.search._SearchRuntime import _SEARCH_RUNTIME
from wks.services.search import SearchRequest, search_documents


@pytest.fixture
def search_service_env(tmp_path, monkeypatch):
    _SEARCH_RUNTIME.reset()
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass"}},
        },
    )
    docs = write_and_index_search_docs(tmp_path)
    return {"docs": docs}


@pytest.fixture
def search_service_strategy_env(tmp_path, monkeypatch):
    _SEARCH_RUNTIME.reset()
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "default_strategy": "hybrid",
            "strategies": {"hybrid": {"indexes": ["main", "semantic"], "merge": "rrf"}},
            "indexes": {
                "main": {"engine": "textpass"},
                "semantic": {"engine": "textpass", "embedding_model": "test-model"},
            },
        },
    )
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    docs = write_and_index_search_docs(tmp_path)
    for name in SEARCH_DOCS:
        result = run_cmd(index_cmd, "semantic", str(tmp_path / name))
        assert result.success is True
    embed_result = run_cmd(cmd_embed, "semantic", batch_size=8)
    assert embed_result.success is True
    return {"docs": docs}


def test_search_service_returns_ranked_hits(search_service_env):
    """The search service should return ranked lexical hits."""
    response = search_documents(SearchRequest(query="fission yield"))

    assert response.success is True
    assert response.index_name == "main"
    assert response.search_mode == "lexical"
    assert response.hits
    assert "fission" in response.hits[0].text.lower()


def test_search_service_rejects_empty_query(tmp_path, monkeypatch):
    """The search service should reject blank text and image queries."""
    _SEARCH_RUNTIME.reset()
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )

    response = search_documents(SearchRequest())

    assert response.success is False
    assert response.failure_kind == "validation"
    assert response.errors == ["Either query or query_image is required"]


def test_search_service_runs_strategy_search(search_service_strategy_env):
    """The search service should merge strategy results through the shared service layer."""
    response = search_documents(SearchRequest(query="fission", strategy="hybrid"))

    assert response.success is True
    assert response.index_name == "hybrid"
    assert response.search_mode == "combined"
    assert response.hits
