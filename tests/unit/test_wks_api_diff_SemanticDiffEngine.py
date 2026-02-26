"""Unit tests for SemanticDiffEngine."""

import json

import numpy as np
from PIL import Image

from wks.api.diff.SemanticDiffEngine import SemanticDiffEngine


def test_semantic_diff_text_basic(tmp_path, monkeypatch):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("alpha line\nbeta line\n")
    file_b.write_text("alpha line updated\nbeta line\nnew line\n")

    def _fake_embed(self, units, model_name):
        if len(units) == 2:
            return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        return np.array([[0.95, 0.1], [0.0, 1.0], [0.2, 0.8]], dtype=np.float32)

    # Keep matching deterministic and local to this test.
    monkeypatch.setattr("wks.api.diff.SemanticDiffEngine.SemanticDiffEngine._embed_text_units", _fake_embed)

    engine = SemanticDiffEngine()
    raw = engine.diff(file_a, file_b, {"modified_threshold": 0.6, "unchanged_threshold": 0.95})
    report = json.loads(raw)

    assert report["engine"] == "semantic"
    assert report["file_type"] == "text"
    assert report["counts"]["added"] >= 0
    assert "semantic_similarity" in report


def test_semantic_diff_image_basic(tmp_path, monkeypatch):
    file_a = tmp_path / "a.png"
    file_b = tmp_path / "b.png"

    Image.new("RGB", (12, 12), color=(255, 0, 0)).save(file_a)
    Image.new("RGB", (12, 12), color=(245, 5, 0)).save(file_b)

    monkeypatch.setattr(
        "wks.api.diff.SemanticDiffEngine.SemanticDiffEngine._semantic_similarity_image",
        lambda self, img_a, img_b, model_name: 0.96,
    )

    engine = SemanticDiffEngine()
    raw = engine.diff(file_a, file_b, {"pixel_threshold": 5})
    report = json.loads(raw)

    assert report["engine"] == "semantic"
    assert report["file_type"] == "image"
    assert report["semantic_similarity"] == 0.96
    assert "metrics" in report
    assert "mae" in report["metrics"]
