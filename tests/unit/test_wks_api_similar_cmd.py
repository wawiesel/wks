import json
from pathlib import Path

import numpy as np

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.search._SearchRuntime import _SEARCH_RUNTIME
from wks.api.similar.cmd import cmd as similar_cmd


def write_semantic_config(tmp_path, monkeypatch, *, with_index=True) -> None:
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    if with_index:
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


def normalized(values: list[float]) -> list[float]:
    vector = np.asarray(values, dtype=np.float32)
    norm = np.linalg.norm(vector)
    return vector.tolist() if norm == 0 else (vector / norm).tolist()


def fake_embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    mapping = {
        "reactor coolant": normalized([1.0, 0.0, 0.0, 0.0]),
        "fission yield": normalized([0.0, 1.0, 0.0, 0.0]),
    }
    return np.asarray([mapping[text] for text in texts], dtype=np.float32)


def insert_embedding_doc(db, uri: Path, chunk_index: int, text: str, embedding: list[float]) -> None:
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
    write_semantic_config(tmp_path, monkeypatch)
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    _SEARCH_RUNTIME.reset()

    files = {
        "query": tmp_path / "shielding_analysis.md",
        "exact": tmp_path / "copies" / "shielding_analysis_copy.md",
        "near": tmp_path / "copies" / "shielding_analysis_rev2.md",
        "family": tmp_path / "exports" / "shielding_analysis.pdf",
        "topic": tmp_path / "notes" / "reactor_briefing.md",
    }
    files["exact"].parent.mkdir()
    files["family"].parent.mkdir()
    files["topic"].parent.mkdir()
    files["query"].write_text("reactor coolant\nfission yield\n")
    files["exact"].write_text(files["query"].read_text())
    files["near"].write_text("reactor coolant revised\nfission yield revised\n")
    files["family"].write_bytes(b"%PDF-1.4\nprototype\n")
    files["topic"].write_text("reactor operating conditions\nyield briefing\n")

    docs = [
        ("exact", 0, "reactor coolant", normalized([1.0, 0.0, 0.0, 0.0])),
        ("exact", 1, "fission yield", normalized([0.0, 1.0, 0.0, 0.0])),
        ("near", 0, "reactor coolant revised", normalized([0.95, 0.05, 0.0, 0.0])),
        ("near", 1, "fission yield revised", normalized([0.05, 0.95, 0.0, 0.0])),
        ("family", 0, "reactor coolant summary", normalized([1.0, 0.0, 0.0, 0.0])),
        ("family", 1, "appendix schedule", normalized([0.0, 0.0, 1.0, 0.0])),
        ("topic", 0, "reactor operating conditions", normalized([0.6, 0.4, 0.0, 0.0])),
        ("topic", 1, "yield briefing", normalized([0.3, 0.7, 0.0, 0.0])),
    ]
    with Database(WKSConfig.load().database, "index_embeddings") as db:
        for key, chunk_index, text, embedding in docs:
            insert_embedding_doc(db, files[key], chunk_index, text, embedding)

    result = run_cmd(similar_cmd, str(files["query"]), top=10, per_chunk=5, candidates=10, match_threshold=0.8)

    assert result.success is True
    assert result.output["query_chunk_count"] == 2
    hits_by_uri = {hit["uri"]: hit for hit in result.output["hits"]}
    assert hits_by_uri[str(URI.from_path(files["exact"]))]["label"] == "exact_duplicate"
    assert hits_by_uri[str(URI.from_path(files["near"]))]["label"] == "near_duplicate"
    assert hits_by_uri[str(URI.from_path(files["family"]))]["label"] == "same_document_family"
    assert hits_by_uri[str(URI.from_path(files["topic"]))]["label"] == "topic_related"
    assert [hit["label"] for hit in result.output["hits"][:2]] == ["exact_duplicate", "near_duplicate"]

    family_hit = hits_by_uri[str(URI.from_path(files["family"]))]
    assert family_hit["coverage_query"] == 0.5
    assert family_hit["matched_chunks"] == 1
    assert len(family_hit["evidence"]) == 1

    topic_hit = hits_by_uri[str(URI.from_path(files["topic"]))]
    assert topic_hit["matched_chunks"] == 2
    assert topic_hit["mean_similarity"] < 0.88


def test_similar_requires_semantic_index(tmp_path, monkeypatch):
    write_semantic_config(tmp_path, monkeypatch, with_index=False)
    _SEARCH_RUNTIME.reset()

    query_file = tmp_path / "query.md"
    query_file.write_text("reactor coolant\nfission yield\n")

    result = run_cmd(similar_cmd, str(query_file))

    assert result.success is False
    assert "no index section in config" in result.output["errors"][0].lower()
