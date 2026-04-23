"""Tests for document similarity built from chunk-level semantic matches."""

import json
from pathlib import Path

import numpy as np

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.search._SearchRuntime import _SEARCH_RUNTIME
from wks.api.similar.cmd import cmd as similar_cmd


def _write_semantic_config(tmp_path, monkeypatch) -> None:
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["index"] = {
        "default_index": "main",
        "indexes": {
            "main": {
                "engine": "textpass",
                "embedding_model": "test-model",
                "max_tokens": 2,
                "overlap_tokens": 0,
            }
        },
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))


def _normalized(values: list[float]) -> list[float]:
    vector = np.asarray(values, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector.tolist()
    return (vector / norm).tolist()


def _fake_embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    mapping = {
        "reactor coolant": _normalized([1.0, 0.0, 0.0, 0.0]),
        "fission yield": _normalized([0.0, 1.0, 0.0, 0.0]),
    }
    rows = [mapping[text] for text in texts]
    return np.asarray(rows, dtype=np.float32)


def _insert_embedding_doc(
    *,
    db,
    uri: Path,
    chunk_index: int,
    text: str,
    embedding: list[float],
) -> None:
    db.insert_one(
        {
            "index_name": "main",
            "embedding_model": "test-model",
            "uri": str(URI.from_path(uri)),
            "chunk_index": chunk_index,
            "tokens": len(text.split()),
            "text": text,
            "embedding": embedding,
        }
    )


def test_similar_labels_document_families(tmp_path, monkeypatch):
    _write_semantic_config(tmp_path, monkeypatch)
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _fake_embed_texts)
    _SEARCH_RUNTIME.reset()

    query_file = tmp_path / "shielding_analysis.md"
    query_file.write_text("reactor coolant\nfission yield\n")

    exact_file = tmp_path / "copies" / "shielding_analysis_copy.md"
    exact_file.parent.mkdir()
    exact_file.write_text(query_file.read_text())

    near_file = tmp_path / "copies" / "shielding_analysis_rev2.md"
    near_file.write_text("reactor coolant revised\nfission yield revised\n")

    family_file = tmp_path / "exports" / "shielding_analysis.pdf"
    family_file.parent.mkdir()
    family_file.write_bytes(b"%PDF-1.4\nprototype\n")

    topic_file = tmp_path / "notes" / "reactor_briefing.md"
    topic_file.parent.mkdir()
    topic_file.write_text("reactor operating conditions\nyield briefing\n")

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        _insert_embedding_doc(
            db=db,
            uri=exact_file,
            chunk_index=0,
            text="reactor coolant",
            embedding=_normalized([1.0, 0.0, 0.0, 0.0]),
        )
        _insert_embedding_doc(
            db=db,
            uri=exact_file,
            chunk_index=1,
            text="fission yield",
            embedding=_normalized([0.0, 1.0, 0.0, 0.0]),
        )
        _insert_embedding_doc(
            db=db,
            uri=near_file,
            chunk_index=0,
            text="reactor coolant revised",
            embedding=_normalized([0.95, 0.05, 0.0, 0.0]),
        )
        _insert_embedding_doc(
            db=db,
            uri=near_file,
            chunk_index=1,
            text="fission yield revised",
            embedding=_normalized([0.05, 0.95, 0.0, 0.0]),
        )
        _insert_embedding_doc(
            db=db,
            uri=family_file,
            chunk_index=0,
            text="reactor coolant summary",
            embedding=_normalized([1.0, 0.0, 0.0, 0.0]),
        )
        _insert_embedding_doc(
            db=db,
            uri=family_file,
            chunk_index=1,
            text="appendix schedule",
            embedding=_normalized([0.0, 0.0, 1.0, 0.0]),
        )
        _insert_embedding_doc(
            db=db,
            uri=topic_file,
            chunk_index=0,
            text="reactor operating conditions",
            embedding=_normalized([0.6, 0.4, 0.0, 0.0]),
        )
        _insert_embedding_doc(
            db=db,
            uri=topic_file,
            chunk_index=1,
            text="yield briefing",
            embedding=_normalized([0.3, 0.7, 0.0, 0.0]),
        )

    result = run_cmd(similar_cmd, str(query_file), top=10, per_chunk=5, candidates=10, match_threshold=0.8)
    assert result.success is True
    assert result.output["query_chunk_count"] == 2

    hits_by_uri = {hit["uri"]: hit for hit in result.output["hits"]}
    assert hits_by_uri[str(URI.from_path(exact_file))]["label"] == "exact_duplicate"
    assert hits_by_uri[str(URI.from_path(near_file))]["label"] == "near_duplicate"
    assert hits_by_uri[str(URI.from_path(family_file))]["label"] == "same_document_family"
    assert hits_by_uri[str(URI.from_path(topic_file))]["label"] == "topic_related"

    labels = [hit["label"] for hit in result.output["hits"]]
    assert labels[0] == "exact_duplicate"
    assert labels[1] == "near_duplicate"

    family_hit = hits_by_uri[str(URI.from_path(family_file))]
    assert family_hit["coverage_query"] == 0.5
    assert family_hit["matched_chunks"] == 1
    assert len(family_hit["evidence"]) == 1

    topic_hit = hits_by_uri[str(URI.from_path(topic_file))]
    assert topic_hit["matched_chunks"] == 2
    assert topic_hit["mean_similarity"] < 0.88


def test_similar_requires_semantic_index(tmp_path, monkeypatch):
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
    _SEARCH_RUNTIME.reset()

    query_file = tmp_path / "query.md"
    query_file.write_text("reactor coolant\nfission yield\n")

    result = run_cmd(similar_cmd, str(query_file))
    assert result.success is False
    assert "no index section in config" in result.output["errors"][0].lower()
