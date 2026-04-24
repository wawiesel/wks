import json

import numpy as np
from PIL import Image

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.index.cmd import cmd


def make_index_env(tmp_path, monkeypatch, *, indexes=None, extra_engines=None):
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    if extra_engines:
        config_dict["transform"]["engines"].update(extra_engines)
    if indexes is not None:
        config_dict["index"] = indexes

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))
    return tmp_path / "doc.txt"


def default_indexes():
    return {
        "default_index": "main",
        "indexes": {
            "main": {"engine": "textpass"},
            "alt": {"engine": "textpass", "max_tokens": 128, "overlap_tokens": 32},
        },
    }


def test_cmd_index_success_and_aliases(tmp_path, monkeypatch):
    test_file = make_index_env(tmp_path, monkeypatch, indexes=default_indexes())
    test_file.write_text("Nuclear fission products are generated during reactor operation.\n" * 20)

    for target in (str(test_file), str(URI.from_path(test_file)), URI.from_path(test_file)):
        result = run_cmd(cmd, "main", target)
        assert result.success is True
        assert result.output["index_name"] == "main"
        assert result.output["chunk_count"] >= 1
        assert result.output["checksum"] != ""


def test_cmd_index_alt_index(tmp_path, monkeypatch):
    test_file = make_index_env(tmp_path, monkeypatch, indexes=default_indexes())
    test_file.write_text("Nuclear fission products are generated during reactor operation.\n" * 20)

    result = run_cmd(cmd, "alt", str(test_file))
    assert result.success is True
    assert result.output["index_name"] == "alt"
    assert result.output["chunk_count"] >= 1


def test_cmd_index_unknown_index(tmp_path, monkeypatch):
    test_file = make_index_env(tmp_path, monkeypatch, indexes=default_indexes())
    test_file.write_text("content")

    result = run_cmd(cmd, "nonexistent", str(test_file))
    assert result.success is False
    assert "nonexistent" in result.output["errors"][0]


def test_cmd_index_no_config(tmp_path, monkeypatch):
    make_index_env(tmp_path, monkeypatch)
    result = run_cmd(cmd, "main", "/tmp/whatever.txt")
    assert result.success is False
    assert "not configured" in result.result.lower()


def test_cmd_index_file_not_found(tmp_path, monkeypatch):
    make_index_env(tmp_path, monkeypatch, indexes=default_indexes())
    result = run_cmd(cmd, "main", str(tmp_path / "missing.txt"))
    assert result.success is False
    assert "not found" in result.output["errors"][0].lower()


def test_cmd_index_populates_embeddings_for_semantic_index(tmp_path, monkeypatch):
    test_file = make_index_env(
        tmp_path,
        monkeypatch,
        indexes={"default_index": "main", "indexes": {"main": {"engine": "textpass", "embedding_model": "test-model"}}},
    )

    def fake_embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
        del model_name, batch_size
        rows = []
        for text in texts:
            vec = np.array([float(len(text)), 1.0, 0.0], dtype=np.float32)
            norm = np.linalg.norm(vec)
            rows.append((vec / norm if norm > 0 else vec).tolist())
        return np.asarray(rows, dtype=np.float32)

    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed_texts)
    test_file.write_text("Nuclear fission products are generated during reactor operation.\n")

    result = run_cmd(cmd, "main", str(test_file))
    assert result.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        assert db.count_documents({"index_name": "main", "embedding_model": "test-model"}) >= 1


def test_cmd_index_populates_combo_embeddings_for_image_text_index(tmp_path, monkeypatch):
    image_path = tmp_path / "cat.png"
    Image.new("RGB", (24, 24), color=(255, 120, 20)).save(image_path)
    make_index_env(
        tmp_path,
        monkeypatch,
        extra_engines={
            "img_caption": {"type": "imagetext", "data": {"model": "test-caption-model", "max_new_tokens": 16}}
        },
        indexes={
            "default_index": "main",
            "indexes": {
                "main": {
                    "engine": "img_caption",
                    "embedding_model": "test-clip-model",
                    "embedding_mode": "image_text_combo",
                    "image_text_weight": 0.6,
                }
            },
        },
    )

    monkeypatch.setattr(
        "wks.api.transform._imagetext._ImageTextEngine._ImageTextEngine._caption_image",
        lambda self, image_path, model_name, max_new_tokens: f"caption {image_path.stem}",
    )

    def fake_embed_clip_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
        del model_name, batch_size
        rows = []
        for text in texts:
            lower = text.lower()
            vec = np.array([float("cat" in lower), float("mountain" in lower), 1.0], dtype=np.float32)
            rows.append((vec / np.linalg.norm(vec)).tolist())
        return np.asarray(rows, dtype=np.float32)

    def fake_embed_clip_images(image_paths: list, model_name: str, batch_size: int) -> np.ndarray:
        del model_name, batch_size
        rows = []
        for path in image_paths:
            stem = path.stem.lower()
            vec = np.array([1.0, 0.0, 1.0], dtype=np.float32) if "cat" in stem else np.array([0.0, 1.0, 1.0])
            rows.append((vec / np.linalg.norm(vec)).tolist())
        return np.asarray(rows, dtype=np.float32)

    monkeypatch.setattr("wks.api.index._embedding_utils.embed_clip_texts", fake_embed_clip_texts)
    monkeypatch.setattr("wks.api.index._embedding_utils.embed_clip_images", fake_embed_clip_images)

    result = run_cmd(cmd, "main", str(image_path))
    assert result.success is True

    config = WKSConfig.load()
    with Database(config.database, "index_embeddings") as db:
        doc = db.find_one({"index_name": "main", "embedding_model": "test-clip-model"}, {"_id": 0})
    assert doc is not None
    assert doc["embedding_mode"] == "image_text_combo"
    assert len(doc["embedding"]) == 3
