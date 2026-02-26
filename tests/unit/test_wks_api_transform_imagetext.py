"""Tests for imagetext transform engine.

Requirements:
- WKS-TRANSFORM-001
"""

from PIL import Image

from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content


def test_cmd_engine_imagetext_success(tracked_wks_config, tmp_path, monkeypatch):
    config = WKSConfig.load()
    config.transform.engines["img_caption"] = _EngineConfig(
        type="imagetext",
        data={"model": "test-caption-model", "max_new_tokens": 16},
    )

    image_path = tmp_path / "cat.png"
    Image.new("RGB", (16, 16), color=(200, 100, 50)).save(image_path)

    monkeypatch.setattr(
        "wks.api.transform._imagetext._ImageTextEngine._ImageTextEngine._caption_image",
        lambda self, image_path, model_name, max_new_tokens: f"caption:{image_path.name}:{max_new_tokens}",
    )

    result = run_cmd(
        cmd_engine,
        engine="img_caption",
        uri=URI.from_path(image_path),
        overrides={},
    )
    assert result.success is True
    content = get_content(result.output["checksum"])
    assert "caption:cat.png:16" in content
