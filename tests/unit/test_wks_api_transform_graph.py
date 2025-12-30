from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.transform._TransformController import _TransformController
from wks.api.transform._TransformEngine import _TransformEngine


# Mock engine that returns referenced images
class MockImageEngine(_TransformEngine):
    def transform(self, input_path: Path, output_path: Path, options: dict):
        yield "Processing..."
        output_path.write_text("Markdown with images")

        # Simulate an image
        image_uri = "file:///tmp/cache/image1.png"
        return [image_uri]

    def get_extension(self, options):
        return "md"

    def compute_options_hash(self, options):
        return "hash"


def test_transform_updates_graph_with_images(tmp_path, reset_mongomock, monkeypatch):
    """Verify that transform updates the graph with nodes and edges."""

    # Setup DB
    from tests.conftest import minimal_config_dict

    cfg_dict = minimal_config_dict()
    config = WKSConfig(**cfg_dict)

    # Setup Cache
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)

    # Register mock engine
    config.transform.engines["mock_img"] = MagicMock()
    config.transform.engines["mock_img"].type = "mock_img"
    config.transform.engines["mock_img"].data = {}

    # Patch _get_engine_by_type to return our mock
    def mock_get_engine(type_name):
        return MockImageEngine()

    monkeypatch.setattr("wks.api.transform._TransformController._get_engine_by_type", mock_get_engine)

    # Setup Controller
    with Database(config.database) as db:
        # Cast to Any to bypass strict type check for mocked/patched config object in test
        controller = _TransformController(db, cast(Any, config.transform))

        # Create input file
        input_file = tmp_path / "input.pdf"
        input_file.write_text("dummy content")

        # Run transform
        gen = controller.transform(input_file, "mock_img")
        try:
            while True:
                next(gen)
        except StopIteration:
            pass

        # Verify Graph
        # 1. Check Edges
        edges = list(db.get_database()["edges"].find())

        # Expect:
        # Source -> Output (transform)
        # Output -> Image (refers_to)

        types = [e["type"] for e in edges]
        assert "transform" in types
        assert "refers_to" in types

        ref_edge = next(e for e in edges if e["type"] == "refers_to")
        assert ref_edge["target"] == "file:///tmp/cache/image1.png"

        # 2. Check Nodes
        nodes = list(db.get_database()["nodes"].find())
        uris = [n["uri"] for n in nodes]
        assert "file:///tmp/cache/image1.png" in uris
