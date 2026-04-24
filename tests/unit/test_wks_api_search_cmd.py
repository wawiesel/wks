import json
from hashlib import sha256

import numpy as np
import pytest
from PIL import Image

from tests.conftest import run_cmd
from tests.unit._search_test_helpers import fake_embed_texts, setup_search_config, write_and_index_search_docs
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.index._ChunkStore import _ChunkStore
from wks.api.index._EmbeddingStore import _EmbeddingStore
from wks.api.index.cmd import cmd as index_cmd
from wks.api.index.cmd_embed import cmd_embed
from wks.api.search._SearchRuntime import _SEARCH_RUNTIME
from wks.api.search.cmd import cmd as search_cmd


def setup_indexed_search_env(tmp_path, monkeypatch, *, semantic=False):
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "indexes": {
                "main": {"engine": "textpass", **({"embedding_model": "test-model"} if semantic else {})},
            },
        },
    )
    if semantic:
        monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    return {"docs": write_and_index_search_docs(tmp_path)}


def embed_main_index(monkeypatch) -> None:
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    result = run_cmd(cmd_embed, "main", batch_size=8)
    assert result.success is True


def load_embedding_docs():
    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        return list(db.find({"index_name": "main", "embedding_model": "test-model"}, {"_id": 0}))


def test_search_finds_relevant(search_env):
    result = run_cmd(search_cmd, "fission yield")

    assert result.success is True
    assert "fission" in result.output["hits"][0]["text"].lower()


def test_search_returns_scores(search_env):
    result = run_cmd(search_cmd, "reactor")

    assert result.success is True
    assert all(hit["score"] > 0 and "uri" in hit and "text" in hit for hit in result.output["hits"])


def test_search_respects_k(search_env):
    result = run_cmd(search_cmd, "the", k=1)

    assert result.success is True
    assert len(result.output["hits"]) == 1


def test_search_no_match(search_env):
    result = run_cmd(search_cmd, "xyzzyplugh")

    assert result.success is True
    assert result.output["hits"] == []


@pytest.fixture
def search_env(tmp_path, monkeypatch):
    return setup_indexed_search_env(tmp_path, monkeypatch)


@pytest.fixture
def search_env_semantic(tmp_path, monkeypatch):
    return setup_indexed_search_env(tmp_path, monkeypatch, semantic=True)


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


@pytest.mark.parametrize("mutate_index, expected_calls", [(False, 1), (True, 2)])
def test_search_lexical_runtime_cache_behavior(search_env, monkeypatch, tmp_path, mutate_index, expected_calls):
    _SEARCH_RUNTIME.reset()
    call_count = {"count": 0}
    original_get_all = _ChunkStore.get_all

    def counting_get_all(self, index_name: str):
        call_count["count"] += 1
        return original_get_all(self, index_name)

    monkeypatch.setattr(_ChunkStore, "get_all", counting_get_all)

    first = run_cmd(search_cmd, "fission", index="main")
    assert first.success is True
    if mutate_index:
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

    second = run_cmd(search_cmd, "reactor" if not mutate_index else "fission", index="main")

    assert second.success is True
    assert call_count["count"] == expected_calls


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
    embed_main_index(monkeypatch)
    result = run_cmd(search_cmd, "fission")

    assert result.success is True
    assert result.output["search_mode"] == "semantic"
    assert result.output["embedding_model"] == "test-model"
    assert "fission" in result.output["hits"][0]["text"].lower()


@pytest.mark.parametrize("mutate_embeddings, expected_calls", [(False, 1), (True, 2)])
def test_search_semantic_runtime_cache_behavior(search_env_semantic, monkeypatch, mutate_embeddings, expected_calls):
    embed_main_index(monkeypatch)
    _SEARCH_RUNTIME.reset()
    call_count = {"count": 0}
    original_get_all = _EmbeddingStore.get_all

    def counting_get_all(self, index_name: str, embedding_model: str):
        call_count["count"] += 1
        return original_get_all(self, index_name=index_name, embedding_model=embedding_model)

    monkeypatch.setattr(_EmbeddingStore, "get_all", counting_get_all)

    first = run_cmd(search_cmd, "fission", index="main")
    assert first.success is True
    if mutate_embeddings:
        docs = load_embedding_docs()
        duplicate = dict(docs[0])
        duplicate["uri"] = str(URI.from_any(duplicate["uri"]).path.with_name("fission-runtime-copy.txt"))
        duplicate["chunk_index"] = 4242
        with Database(WKSConfig.load().database, "index_embeddings") as db:
            db.insert_one(duplicate)

    second = run_cmd(search_cmd, "reactor" if not mutate_embeddings else "fission", index="main")

    assert second.success is True
    assert call_count["count"] == expected_calls


def test_search_semantic_requires_embeddings(search_env_semantic):
    with Database(WKSConfig.load().database, "index_embeddings") as db:
        db.delete_many({"index_name": "main", "embedding_model": "test-model"})

    result = run_cmd(search_cmd, "fission")

    assert result.success is False
    assert "no embeddings found" in result.output["errors"][0].lower()


@pytest.mark.parametrize("kind", ["canonical_uri", "text_hash"])
def test_search_semantic_dedupes_hits(search_env_semantic, monkeypatch, kind):
    embed_main_index(monkeypatch)
    docs = load_embedding_docs()
    duplicate = dict(docs[0])
    if kind == "canonical_uri":
        duplicate.update(
            {
                "uri": str(URI.from_any(docs[0]["uri"]).path),
                "chunk_index": 999,
                "text": "duplicate entry via non-canonical uri form",
            }
        )
    else:
        duplicate.update(
            {
                "uri": str(URI.from_any(docs[0]["uri"]).path.with_name("fission-copy.txt")),
                "chunk_index": 1001,
            }
        )

    with Database(WKSConfig.load().database, "index_embeddings") as db:
        db.insert_one(duplicate)

    result = run_cmd(search_cmd, "fission", k=10)
    if kind == "canonical_uri":
        values = [str(URI.from_any(hit["uri"])) for hit in result.output["hits"]]
    else:
        values = [sha256(hit["text"].encode("utf-8")).hexdigest() for hit in result.output["hits"]]

    assert result.success is True
    assert len(values) == len(set(values))


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

    def fake_embed_clip_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
        rows = []
        for text in texts:
            lower = text.lower()
            vec = np.array([float("cat" in lower), float("mountain" in lower), 1.0], dtype=np.float32)
            rows.append((vec / np.linalg.norm(vec)).tolist())
        return np.asarray(rows, dtype=np.float32)

    def fake_embed_clip_images(image_paths: list, model_name: str, batch_size: int) -> np.ndarray:
        rows = []
        for image_path in image_paths:
            stem = image_path.stem.lower()
            vec = np.array([1.0, 0.0, 1.0], dtype=np.float32) if "cat" in stem else np.array([0.0, 1.0, 1.0])
            rows.append((vec / np.linalg.norm(vec)).tolist())
        return np.asarray(rows, dtype=np.float32)

    monkeypatch.setattr("wks.api.index._embedding_utils.embed_clip_texts", fake_embed_clip_texts)
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_clip_images", fake_embed_clip_images)

    cat_image = tmp_path / "cat.png"
    mountain_image = tmp_path / "mountain.png"
    Image.new("RGB", (16, 16), color=(220, 120, 40)).save(cat_image)
    Image.new("RGB", (16, 16), color=(60, 120, 220)).save(mountain_image)
    for image_path in (cat_image, mountain_image):
        result = run_cmd(index_cmd, "main", str(image_path))
        assert result.success is True
    return {"cat_image": cat_image}


@pytest.mark.parametrize(
    ("query", "query_image"),
    [("cat", None), ("", "cat_image")],
)
def test_search_semantic_image_queries(search_env_semantic_image, query, query_image):
    kwargs: dict[str, object] = {"k": 2}
    if query_image:
        kwargs["query_image"] = str(search_env_semantic_image[query_image])

    result = run_cmd(search_cmd, query, **kwargs)

    assert result.success is True
    assert result.output["search_mode"] == "semantic"
    assert "cat.png" in result.output["hits"][0]["uri"]


def test_search_semantic_path_segment_boost(tmp_path, monkeypatch):
    setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass", "embedding_model": "test-model"}},
        },
    )

    monkeypatch.setattr(
        "wks.api.index._embedding_utils.embed_texts",
        lambda texts, model_name, batch_size: np.tile(np.array([1.0, 0.0, 0.0], dtype=np.float32), (len(texts), 1)),
    )
    for path in (tmp_path / "agents.txt", tmp_path / "other.txt"):
        path.write_text(f"Some generic content about topics in {path.stem}.\n")
        assert run_cmd(index_cmd, "main", str(path)).success is True

    assert run_cmd(cmd_embed, "main", batch_size=8).success is True
    result = run_cmd(search_cmd, "agents content", k=2)

    assert result.success is True
    assert len(result.output["hits"]) == 2
    assert "agents.txt" in result.output["hits"][0]["uri"]
