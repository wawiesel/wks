"""Index embedding command tests."""

import json

import numpy as np
from PIL import Image

from tests.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.index.cmd import cmd as index_cmd
from wks.api.index.cmd_embed import cmd_embed


def _make_index_env(tmp_path, monkeypatch):
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["index"] = {
        "default_index": "main",
        "indexes": {"main": {"engine": "textpass", "embedding_model": "test-model"}},
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))


def _fake_embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    rows: list[list[float]] = []
    for text in texts:
        vec = np.array(
            [
                float(len(text)),
                float(text.lower().count("fission")),
                float(text.lower().count("python")),
            ],
            dtype=np.float32,
        )
        norm = np.linalg.norm(vec)
        rows.append((vec / norm if norm > 0 else vec).tolist())
    return np.asarray(rows, dtype=np.float32)


def test_cmd_embed_success(tmp_path, monkeypatch):
    _make_index_env(tmp_path, monkeypatch)
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", _fake_embed_texts)

    doc = tmp_path / "doc.txt"
    doc.write_text("Nuclear fission products are generated during reactor operation.\n")
    idx_result = run_cmd(index_cmd, "main", str(doc))
    assert idx_result.success is True

    result = run_cmd(cmd_embed, "main", batch_size=8)
    assert result.success is True
    assert result.output["index_name"] == "main"
    assert result.output["embedding_model"] == "test-model"
    assert result.output["chunk_count"] >= 1
    assert result.output["dimensions"] == 3

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        count = db.count_documents({"index_name": "main", "embedding_model": "test-model"})
    assert count >= 1


def test_cmd_embed_empty_index(tmp_path, monkeypatch):
    _make_index_env(tmp_path, monkeypatch)
    result = run_cmd(cmd_embed, "main", batch_size=8)
    assert result.success is False
    assert "empty" in result.output["errors"][0].lower()


def test_cmd_embed_requires_embedding_model(tmp_path, monkeypatch):
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["index"] = {"default_index": "main", "indexes": {"main": {"engine": "textpass"}}}

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    result = run_cmd(cmd_embed, "main", batch_size=8)
    assert result.success is False
    assert "no embedding_model" in result.result.lower()


def test_cmd_embed_image_text_combo_success(tmp_path, monkeypatch):
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
                "image_text_weight": 0.5,
            }
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
    idx_result = run_cmd(index_cmd, "main", str(image_path))
    assert idx_result.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        db.delete_many({"index_name": "main", "embedding_model": "test-clip-model"})

    result = run_cmd(cmd_embed, "main", batch_size=8)
    assert result.success is True
    assert result.output["embedding_model"] == "test-clip-model"
    assert result.output["dimensions"] == 3
