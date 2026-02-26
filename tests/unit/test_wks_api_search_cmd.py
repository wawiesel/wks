"""Search command tests.

Tests the public cmd(query, index, k) function which performs
BM25 search over a named index.
"""

import json
from hashlib import sha256

import numpy as np
import pytest
from PIL import Image

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.index.cmd import cmd as index_cmd
from wks.api.index.cmd_embed import cmd_embed
from wks.api.search.cmd import cmd as search_cmd

_SEARCH_DOCS = {
    "fission.txt": (
        "Nuclear fission products are generated during reactor operation.\n"
        "The fission yield depends on the fissile isotope and neutron energy.\n"
    ),
    "python.txt": (
        "Python programming language is used for scientific computing.\n"
        "Libraries like numpy and scipy provide numerical methods.\n"
    ),
    "coolant.txt": (
        "Reactor coolant systems maintain safe operating temperatures.\n"
        "The primary loop transfers heat from the reactor core.\n"
    ),
}


def _write_and_index_search_docs(tmp_path):
    """Write test documents and index them; returns list of paths."""
    docs = []
    for name, content in _SEARCH_DOCS.items():
        doc = tmp_path / name
        doc.write_text(content)
        result = run_cmd(index_cmd, "main", str(doc))
        assert result.success is True
        docs.append(doc)
    return docs


def _setup_search_config(tmp_path, monkeypatch, *, index_config):
    """Write a WKS config with the given index section."""
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["index"] = index_config

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))
    return config_dict


@pytest.fixture
def search_env(tmp_path, monkeypatch):
    """Build an index with several documents for search testing."""
    _setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass"}},
        },
    )
    docs = _write_and_index_search_docs(tmp_path)
    return {"docs": docs}


@pytest.fixture
def search_env_semantic(tmp_path, monkeypatch):
    """Build an index configured for semantic search with embeddings."""
    _setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass", "embedding_model": "test-model"}},
        },
    )
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _fake_embed_texts)
    docs = _write_and_index_search_docs(tmp_path)
    return {"docs": docs}


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


def test_search_empty_query_returns_no_hits(tmp_path, monkeypatch):
    _setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )

    result = run_cmd(search_cmd, "")
    assert result.success is True
    assert result.output["errors"] == []
    assert result.output["hits"] == []


def test_search_lexical_rejects_query_image(search_env):
    result = run_cmd(search_cmd, "", query_image="file:///tmp/example.png")
    assert result.success is False
    assert "query_image" in result.output["errors"][0]


def test_search_lexical_dedupe_fills_k_from_ranked_candidates(tmp_path, monkeypatch):
    _setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )

    config = WKSConfig.load()
    with Database(config.database, "index") as db:
        db.insert_many(
            [
                {
                    "index_name": "main",
                    "uri": str(tmp_path / "a.txt"),
                    "chunk_index": 0,
                    "text": "focus target value",
                    "tokens": 3,
                    "is_continuation": False,
                },
                {
                    "index_name": "main",
                    "uri": str(tmp_path / "a.txt"),
                    "chunk_index": 1,
                    "text": "focus target value extra",
                    "tokens": 4,
                    "is_continuation": False,
                },
                {
                    "index_name": "main",
                    "uri": str(tmp_path / "b.txt"),
                    "chunk_index": 0,
                    "text": "focus target value second doc",
                    "tokens": 5,
                    "is_continuation": False,
                },
                {
                    "index_name": "main",
                    "uri": str(tmp_path / "c.txt"),
                    "chunk_index": 0,
                    "text": "focus target value third doc",
                    "tokens": 5,
                    "is_continuation": False,
                },
            ]
        )

    result = run_cmd(search_cmd, "focus target value", k=3)
    assert result.success is True
    assert len(result.output["hits"]) == 3


def test_search_empty_index(tmp_path, monkeypatch):
    _setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )

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

    # Intentionally omits index config to test the "not configured" path
    result = run_cmd(search_cmd, "anything")
    assert result.success is False
    assert "not configured" in result.result.lower()


def _fake_embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    rows: list[list[float]] = []
    for text in texts:
        lower = text.lower()
        vec = np.array(
            [
                float(lower.count("fission")),
                float(lower.count("python")),
                float(lower.count("reactor")),
            ],
            dtype=np.float32,
        )
        norm = np.linalg.norm(vec)
        rows.append((vec / norm if norm > 0 else vec).tolist())
    return np.asarray(rows, dtype=np.float32)


def test_search_semantic_finds_relevant(search_env_semantic, monkeypatch):
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _fake_embed_texts)
    embed_res = run_cmd(cmd_embed, "main", batch_size=8)
    assert embed_res.success is True

    result = run_cmd(search_cmd, "fission")
    assert result.success is True
    assert result.output["search_mode"] == "semantic"
    assert result.output["embedding_model"] == "test-model"
    assert len(result.output["hits"]) > 0
    assert "fission" in result.output["hits"][0]["text"].lower()


def test_search_semantic_requires_embeddings(search_env_semantic):
    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        db.delete_many({"index_name": "main", "embedding_model": "test-model"})

    result = run_cmd(search_cmd, "fission")
    assert result.success is False
    assert "no embeddings found" in result.output["errors"][0].lower()


def test_search_semantic_dedupes_canonical_uri(search_env_semantic, monkeypatch):
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _fake_embed_texts)
    embed_res = run_cmd(cmd_embed, "main", batch_size=8)
    assert embed_res.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        docs = list(
            db.find(
                {"index_name": "main", "embedding_model": "test-model"},
                {"_id": 0},
            )
        )
        assert len(docs) > 0
        duplicate = dict(docs[0])
        duplicate["uri"] = str(URI.from_any(docs[0]["uri"]).path)
        duplicate["chunk_index"] = 999
        duplicate["text"] = "duplicate entry via non-canonical uri form"
        db.insert_one(duplicate)

    result = run_cmd(search_cmd, "fission", k=10)
    assert result.success is True
    canonical_uris = [str(URI.from_any(hit["uri"])) for hit in result.output["hits"]]
    assert len(canonical_uris) == len(set(canonical_uris))


def test_search_semantic_dedupes_text_hash(search_env_semantic, monkeypatch):
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _fake_embed_texts)
    embed_res = run_cmd(cmd_embed, "main", batch_size=8)
    assert embed_res.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        docs = list(
            db.find(
                {"index_name": "main", "embedding_model": "test-model"},
                {"_id": 0},
            )
        )
        assert len(docs) > 0
        duplicate = dict(docs[0])
        duplicate_path = URI.from_any(docs[0]["uri"]).path.with_name("fission-copy.txt")
        duplicate["uri"] = str(duplicate_path)
        duplicate["chunk_index"] = 1001
        db.insert_one(duplicate)

    result = run_cmd(search_cmd, "fission", k=10)
    assert result.success is True
    content_hashes = [sha256(hit["text"].encode("utf-8")).hexdigest() for hit in result.output["hits"]]
    assert len(content_hashes) == len(set(content_hashes))


@pytest.fixture
def search_env_semantic_image(tmp_path, monkeypatch):
    """Build an image-text combo semantic index with two images."""
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["transform"]["engines"]["img_caption"] = {
        "type": "imagetext",
        "data": {"model": "test-caption-model", "max_new_tokens": 16},
    }
    config_dict["index"] = {
        "default_index": "main",
        "indexes": {
            "main": {
                "engine": "img_caption",
                "embedding_model": "test-clip-model",
                "embedding_mode": "image_text_combo",
                "image_text_weight": 0.6,
            }
        },
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    monkeypatch.setattr(
        "wks.api.transform._imagetext._ImageTextEngine._ImageTextEngine._caption_image",
        lambda self, image_path, model_name, max_new_tokens: "cat animal"
        if "cat" in image_path.stem.lower()
        else "mountain landscape",
    )

    def _fake_embed_clip_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
        rows = []
        for text in texts:
            lower = text.lower()
            vec = np.array([float("cat" in lower), float("mountain" in lower), 1.0], dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            rows.append(vec.tolist())
        return np.asarray(rows, dtype=np.float32)

    def _fake_embed_clip_images(image_paths: list, model_name: str, batch_size: int) -> np.ndarray:
        rows = []
        for image_path in image_paths:
            stem = image_path.stem.lower()
            vec = np.array([1.0, 0.0, 1.0], dtype=np.float32) if "cat" in stem else np.array([0.0, 1.0, 1.0])
            vec = vec / np.linalg.norm(vec)
            rows.append(vec.tolist())
        return np.asarray(rows, dtype=np.float32)

    monkeypatch.setattr("wks.api.index._embedding_utils.embed_clip_texts", _fake_embed_clip_texts)
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_clip_images", _fake_embed_clip_images)

    cat_image = tmp_path / "cat.png"
    mountain_image = tmp_path / "mountain.png"
    Image.new("RGB", (16, 16), color=(220, 120, 40)).save(cat_image)
    Image.new("RGB", (16, 16), color=(60, 120, 220)).save(mountain_image)

    for image_path in [cat_image, mountain_image]:
        result = run_cmd(index_cmd, "main", str(image_path))
        assert result.success is True

    return {"cat_image": cat_image, "mountain_image": mountain_image}


def test_search_semantic_image_text_query(search_env_semantic_image):
    result = run_cmd(search_cmd, "cat", k=2)
    assert result.success is True
    assert result.output["search_mode"] == "semantic"
    assert len(result.output["hits"]) > 0
    assert "cat.png" in result.output["hits"][0]["uri"]


def test_search_semantic_image_query(search_env_semantic_image):
    result = run_cmd(search_cmd, "", query_image=str(search_env_semantic_image["cat_image"]), k=2)
    assert result.success is True
    assert result.output["search_mode"] == "semantic"
    assert len(result.output["hits"]) > 0
    assert "cat.png" in result.output["hits"][0]["uri"]
