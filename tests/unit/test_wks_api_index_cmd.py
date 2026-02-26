"""Index command tests.

Tests the public cmd(name, uri) function which transforms, chunks,
and stores a document in a named index.
"""

import json

import numpy as np
from PIL import Image

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
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


def test_cmd_index_populates_embeddings_for_semantic_index(tmp_path, monkeypatch):
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["index"] = {
        "default_index": "main",
        "indexes": {
            "main": {"engine": "textpass", "embedding_model": "test-model"},
        },
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    def _fake_embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
        rows = []
        for text in texts:
            vec = np.array([float(len(text)), 1.0, 0.0], dtype=np.float32)
            norm = np.linalg.norm(vec)
            rows.append((vec / norm if norm > 0 else vec).tolist())
        return np.asarray(rows, dtype=np.float32)

    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _fake_embed_texts)

    test_file = tmp_path / "doc.txt"
    test_file.write_text("Nuclear fission products are generated during reactor operation.\n")
    result = run_cmd(cmd, "main", str(test_file))
    assert result.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        count = db.count_documents({"index_name": "main", "embedding_model": "test-model"})
    assert count >= 1


def test_cmd_index_populates_combo_embeddings_for_image_text_index(tmp_path, monkeypatch):
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
            },
        },
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    monkeypatch.setattr(
        "wks.api.transform._imagetext._ImageTextEngine._ImageTextEngine._caption_image",
        lambda self, image_path, model_name, max_new_tokens: f"caption {image_path.stem}",
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

    image_path = tmp_path / "cat.png"
    Image.new("RGB", (24, 24), color=(255, 120, 20)).save(image_path)
    result = run_cmd(cmd, "main", str(image_path))
    assert result.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        doc = db.find_one({"index_name": "main", "embedding_model": "test-clip-model"}, {"_id": 0})
    assert doc is not None
    assert doc["embedding_mode"] == "image_text_combo"
    assert len(doc["embedding"]) == 3
