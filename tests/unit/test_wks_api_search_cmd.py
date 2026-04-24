import json
from hashlib import sha256

import numpy as np
import pytest
from PIL import Image

from tests.conftest import run_cmd
from tests.unit._search_test_helpers import (
    fake_embed_texts,
    setup_search_config,
    write_and_index_search_docs,
)
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.index._ChunkStore import _ChunkStore
from wks.api.index._EmbeddingStore import _EmbeddingStore
from wks.api.index.cmd import cmd as index_cmd
from wks.api.index.cmd_embed import cmd_embed
from wks.api.search._SearchRuntime import _SEARCH_RUNTIME
from wks.api.search.cmd import cmd as search_cmd


@pytest.fixture
def search_env(tmp_path, monkeypatch):
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
def search_env_semantic(tmp_path, monkeypatch):
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass", "embedding_model": "test-model"}},
        },
    )
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    docs = write_and_index_search_docs(tmp_path)
    return {"docs": docs}


def test_search_finds_relevant(search_env):
    result = run_cmd(search_cmd, "fission yield")
    assert result.success is True
    assert len(result.output["hits"]) > 0
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


def test_search_empty_query_requires_query_or_image(tmp_path, monkeypatch):
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )

    result = run_cmd(search_cmd, "")
    assert result.success is False
    assert result.output["errors"] == ["Either query or query_image is required"]
    assert result.output["hits"] == []


def test_search_lexical_rejects_query_image(search_env):
    result = run_cmd(search_cmd, "", query_image="file:///tmp/example.png")
    assert result.success is False
    assert "query_image" in result.output["errors"][0]


def test_search_lexical_dedupe_fills_k_from_ranked_candidates(tmp_path, monkeypatch):
    setup_search_config(
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
    setup_search_config(
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


def test_search_lexical_runtime_reuses_hot_index_state(search_env, monkeypatch):
    _SEARCH_RUNTIME.reset()
    call_count = {"count": 0}
    original_get_all = _ChunkStore.get_all

    def _counting_get_all(self, index_name: str):
        call_count["count"] += 1
        return original_get_all(self, index_name)

    monkeypatch.setattr(_ChunkStore, "get_all", _counting_get_all)

    first = run_cmd(search_cmd, "fission", index="main")
    second = run_cmd(search_cmd, "reactor", index="main")

    assert first.success is True
    assert second.success is True
    assert call_count["count"] == 1


def test_search_lexical_runtime_invalidates_on_index_change(search_env, monkeypatch, tmp_path):
    _SEARCH_RUNTIME.reset()
    call_count = {"count": 0}
    original_get_all = _ChunkStore.get_all

    def _counting_get_all(self, index_name: str):
        call_count["count"] += 1
        return original_get_all(self, index_name)

    monkeypatch.setattr(_ChunkStore, "get_all", _counting_get_all)

    first = run_cmd(search_cmd, "fission", index="main")
    assert first.success is True

    config = WKSConfig.load()
    with Database(config.database, "index") as db:
        db.insert_one(
            {
                "index_name": "main",
                "uri": str(tmp_path / "new-doc.txt"),
                "chunk_index": 0,
                "text": "new lexical content about fission products",
                "tokens": 6,
                "is_continuation": False,
            }
        )

    second = run_cmd(search_cmd, "fission", index="main")
    assert second.success is True
    assert call_count["count"] == 2


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


def test_search_semantic_finds_relevant(search_env_semantic, monkeypatch):
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    embed_res = run_cmd(cmd_embed, "main", batch_size=8)
    assert embed_res.success is True

    result = run_cmd(search_cmd, "fission")
    assert result.success is True
    assert result.output["search_mode"] == "semantic"
    assert result.output["embedding_model"] == "test-model"
    assert len(result.output["hits"]) > 0
    assert "fission" in result.output["hits"][0]["text"].lower()


def test_search_semantic_runtime_reuses_hot_index_state(search_env_semantic, monkeypatch):
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    embed_res = run_cmd(cmd_embed, "main", batch_size=8)
    assert embed_res.success is True

    _SEARCH_RUNTIME.reset()
    call_count = {"count": 0}
    original_get_all = _EmbeddingStore.get_all

    def _counting_get_all(self, index_name: str, embedding_model: str):
        call_count["count"] += 1
        return original_get_all(self, index_name=index_name, embedding_model=embedding_model)

    monkeypatch.setattr(_EmbeddingStore, "get_all", _counting_get_all)

    first = run_cmd(search_cmd, "fission", index="main")
    second = run_cmd(search_cmd, "reactor", index="main")

    assert first.success is True
    assert second.success is True
    assert call_count["count"] == 1


def test_search_semantic_runtime_invalidates_on_embedding_change(search_env_semantic, monkeypatch):
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    embed_res = run_cmd(cmd_embed, "main", batch_size=8)
    assert embed_res.success is True

    _SEARCH_RUNTIME.reset()
    call_count = {"count": 0}
    original_get_all = _EmbeddingStore.get_all

    def _counting_get_all(self, index_name: str, embedding_model: str):
        call_count["count"] += 1
        return original_get_all(self, index_name=index_name, embedding_model=embedding_model)

    monkeypatch.setattr(_EmbeddingStore, "get_all", _counting_get_all)

    first = run_cmd(search_cmd, "fission", index="main")
    assert first.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        docs = list(
            db.find(
                {"index_name": "main", "embedding_model": "test-model"},
                {"_id": 0},
            )
        )
        duplicate = dict(docs[0])
        duplicate["uri"] = str(URI.from_any(duplicate["uri"]).path.with_name("fission-runtime-copy.txt"))
        duplicate["chunk_index"] = 4242
        db.insert_one(duplicate)

    second = run_cmd(search_cmd, "fission", index="main")
    assert second.success is True
    assert call_count["count"] == 2


def test_search_semantic_requires_embeddings(search_env_semantic):
    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        db.delete_many({"index_name": "main", "embedding_model": "test-model"})

    result = run_cmd(search_cmd, "fission")
    assert result.success is False
    assert "no embeddings found" in result.output["errors"][0].lower()


def test_search_semantic_dedupes_canonical_uri(search_env_semantic, monkeypatch):
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
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
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
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
        lambda self, image_path, model_name, max_new_tokens: (
            "cat animal" if "cat" in image_path.stem.lower() else "mountain landscape"
        ),
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


def test_search_semantic_path_segment_boost(tmp_path, monkeypatch):
    """Path-segment boost elevates results whose URI filename matches a query term."""
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass", "embedding_model": "test-model"}},
        },
    )

    def _uniform_embed(texts, model_name, batch_size):
        vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        return np.tile(vec, (len(texts), 1))

    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _uniform_embed)

    agents_doc = tmp_path / "agents.txt"
    agents_doc.write_text("Some generic content about topics in agents.\n")
    other_doc = tmp_path / "other.txt"
    other_doc.write_text("Some generic content about topics in other.\n")

    for doc in [agents_doc, other_doc]:
        result = run_cmd(index_cmd, "main", str(doc))
        assert result.success is True

    embed_res = run_cmd(cmd_embed, "main", batch_size=8)
    assert embed_res.success is True

    result = run_cmd(search_cmd, "agents content", k=2)
    assert result.success is True
    assert len(result.output["hits"]) == 2
    assert "agents.txt" in result.output["hits"][0]["uri"], (
        f"Expected agents.txt first, got: {result.output['hits'][0]['uri']}"
    )
