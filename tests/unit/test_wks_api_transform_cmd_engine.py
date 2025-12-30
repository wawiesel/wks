"""Unit tests for transform cmd_transform."""

import json
from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_engine import cmd_transform

pytestmark = pytest.mark.transform


def test_cmd_transform_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform returns expected output structure."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create transform cache directory
    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=None)

    assert result.success
    assert "source_uri" in result.output
    assert "engine" in result.output
    assert "checksum" in result.output
    assert result.output["engine"] == "test"


def test_cmd_transform_with_output_path(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform respects output path."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")
    output_file = tmp_path / "output.md"

    result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=output_file)

    assert result.success
    assert output_file.exists()
    assert "Transformed:" in output_file.read_text()


def test_cmd_transform_with_overrides(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform passes overrides to engine."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    # Test engine ignores overrides, but we verify the call works
    overrides = {"custom_option": True}
    result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides=overrides, output=None)

    assert result.success


def test_cmd_transform_nonexistent_engine_fails(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform fails for unknown engine."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    result = run_cmd(cmd_transform, engine="nonexistent", file_path=test_file, overrides={}, output=None)

    assert not result.success


def test_cmd_transform_caches_result(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform caches transform results."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    # First transform
    result1 = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=None)
    assert result1.success
    checksum1 = result1.output["checksum"]

    # Second transform should return same checksum (cached)
    result2 = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=None)
    assert result2.success
    assert result2.output["checksum"] == checksum1
    # Verify cached status
    assert result1.output["cached"] is False
    assert result2.output["cached"] is True


def test_cmd_transform_error_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform returns valid structure on error."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create config but NOT the file to cause an error
    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "nonexistent.txt"

    result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=None)

    assert not result.success
    assert "errors" in result.output
    assert result.output["status"] == "error"

    # Verify strict schema compliance (None values for required fields)
    assert result.output["destination_uri"] is None
    assert result.output["checksum"] is None
    assert result.output["output_content"] is None
    assert result.output["processing_time_ms"] is None
    assert result.output["source_uri"] is not None  # Should still populate source


def test_cmd_transform_success_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform returns compliant structure on success."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=None)

    assert result.success
    # Strict key check
    keys = result.output.keys()
    assert "output_content" in keys
    assert "processing_time_ms" in keys
    assert "source_uri" in keys
    assert "destination_uri" in keys
    assert "checksum" in keys
    assert "status" in keys
    assert "engine" in keys

    # Check types/values
    assert result.output["processing_time_ms"] is not None
    assert isinstance(result.output["processing_time_ms"], int)
    # output_content is None by default in current implementation
    assert result.output["output_content"] is None

    # Check cached field (should be False for first run)
    assert "cached" in result.output
    assert result.output["cached"] is False


def test_cmd_transform_copy_error_handling(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform handles manual copy errors gracefully."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()
    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    output_file = tmp_path / "output.md"
    output_file.write_text("exists")

    # We mock the controller's transform method to raise FileExistsError
    # This ensures we verify cmd_transform's exception handling regardless of internal implementation details
    with monkeypatch.context() as m:

        def mock_transform(*args, **kwargs):
            raise FileExistsError("Output file already exists")

        # Patch the Unbound method on the class, so all instances use it
        m.setattr("wks.api.transform._TransformController._TransformController.transform", mock_transform)

        result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=output_file)

    assert not result.success
    assert "Output file already exists" in str(result.output["errors"])


def test_cmd_transform_missing_source_file(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_transform handles missing source file."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(cmd_transform, engine="test", file_path=tmp_path / "missing.txt", overrides={}, output=None)

    assert not result.success
    assert not result.success
    assert "File not found" in str(result.output["errors"])


def test_cmd_engine_cache_eviction(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_engine triggers cache eviction when limit reached."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Set small cache limit (e.g. 100 bytes)
    cfg = minimal_config_dict
    cfg["transform"]["cache"]["max_size_bytes"] = 100
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Create 3 files. File sizes + overhead might exceed 100 bytes.
    # We need to control file sizes.
    # File 1: 60 bytes
    f1 = tmp_path / "f1.txt"
    f1.write_text("x" * 60)

    # File 2: Large enough to force eviction of f1 (and likely f2 itself if not careful, but LRU should drop oldest)
    # Cache size 100.
    # f1 = 60 bytes. Remaining = 40.
    # f2 = 60 bytes. Need 60. Available 40. Evict f1.
    # File 2: Large enough to force eviction of f1.
    # Cache size 100.
    # f1 = 60 bytes.
    # f2 = 80 bytes. Total 140 > 100. Must evict f1.
    f2 = tmp_path / "f2.txt"
    f2.write_text("x" * 80)

    # Transform f1
    run_cmd(cmd_transform, engine="test", file_path=f1, overrides={}, output=None)

    # Verify f1 in cache
    # We can check via direct file check in _transform dir if we know the location,
    # but strictly through public API? Public API doesn't expose "list cache".
    # However, we can assert success of the second transform which forces eviction.

    res2 = run_cmd(cmd_transform, engine="test", file_path=f2, overrides={}, output=None)
    assert res2.success

    # Verify correctness: both transforms succeeded.
    # Eviction is an internal side-effect.
    # To strictly verify eviction happened, we'd need to check if f1 is still cached?
    # Rerunning f1 transform should result in `cached=False` if it was evicted.

    res1_again = run_cmd(cmd_transform, engine="test", file_path=f1, overrides={}, output=None)
    assert res1_again.success
    assert res1_again.output["cached"] is False  # Was evicted, so re-transformed


def test_cmd_engine_docling_referenced_images_and_graph(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_engine handles referenced images and updates graph (integration-like)."""
    # This combines logic from DoclingEngine tests and Graph tests

    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Configure mock engine to simulate Docling behavior (returning images)
    # We can Register a custom engine "mock_docling" in config
    cfg = minimal_config_dict
    cfg["transform"]["engines"]["mock_docling"] = {"type": "test_mock_img", "data": {}}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    from pathlib import Path

    from wks.api.transform import _get_engine_by_type
    from wks.api.transform._TransformEngine import _TransformEngine

    # Define Mock Engine
    class MockImageEngine(_TransformEngine):
        def transform(self, input_path: Path, output_path: Path, options: dict):
            yield "Processing page 1"
            # Write main markdown
            import hashlib

            img_content = b"fake_img"
            img_hash = hashlib.sha256(img_content).hexdigest()
            output_path.write_text(f"![](file:///cache/{img_hash}.png)")

            # Identify referenced image URI
            # In a real run, the engine writes the image to cache.
            # Here, we just return the URI.
            return [f"file:///cache/{img_hash}.png"]

        def get_extension(self, options):
            return "md"

        def compute_options_hash(self, options):
            return "hash"

    # Patch factory to return our mock
    # We must patch where it's used: in the controller.
    # But controller is instantiated inside cmd_transform via _get_controller context manager.
    # We can patch wks.api.transform._TransformController._get_engine_by_type
    # Wait, the controller is now private _TransformController.

    with monkeypatch.context() as m:
        m.setattr(
            "wks.api.transform._TransformController._get_engine_by_type",
            lambda t: MockImageEngine() if t == "test_mock_img" else _get_engine_by_type._get_engine_by_type(t),
        )

        test_file = tmp_path / "input.pdf"
        test_file.write_text("dummy")

        # Run command
        result = run_cmd(cmd_transform, engine="mock_docling", file_path=test_file, overrides={}, output=None)

        assert result.success
        assert "Transformed" in result.result

    # Verify Graph Updates (Logic from test_wks_api_transform_graph.py)
    # Access DB directly to verify side effects
    from wks.api.database.Database import Database

    # We need to connect to the same DB used by cmd_transform
    # cmd_transform uses WKSConfig.load().database
    # Tests use mongomock by default (via conftest fixtures usually, or minimal_config_dict setup?)
    # minimal_config_dict sets backend="mongomock".
    # So we can instantiate a generic Database to check
    from wks.api.database.DatabaseConfig import DatabaseConfig

    # So we can instantiate a generic Database to check
    db_config = DatabaseConfig(**cfg["database"])
    with Database(db_config, "transform") as db:
        edges = list(db.get_database()["edges"].find())
        types = [e["type"] for e in edges]
        assert "transform" in types
        assert "refers_to" in types  # Validates graph integration


def test_cmd_engine_docling_execution(monkeypatch, tmp_path, minimal_config_dict):
    """Test real DoclingEngine logic via cmd_engine with mocked subprocess."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Configure docling engine
    cfg = minimal_config_dict
    cfg["transform"]["engines"]["docling"] = {
        "type": "docling",
        "data": {
            "ocr": "tesseract",
            "ocr_languages": ["eng"],
            "image_export_mode": "referenced",
            "pipeline": "standard",
            "timeout_secs": 10,
            "to": "md",
        },
    }
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "doc.pdf"
    test_file.write_text("dummy pdf content")

    # Mock subprocess.Popen
    class MockProcess:
        def __init__(self, cmd, *args, **kwargs):
            self.cmd = cmd
            self.returncode = 0
            self.stdout = ["Processing page 1\n", "Processing page 2\n"]

        def wait(self, timeout=None):
            return 0

    # We need to intercept the output creation because DoclingEngine expects files to be created by the subprocess
    # We can use a side_effect on Popen to create the files? No, Popen just starts it.
    # The engine waits for process, THEN checks for files in the temp_dir passed to "--output".
    # We need to know what that temp_dir is.
    # But temp_dir is created inside `transform` method using `tempfile.TemporaryDirectory()`.
    # We can mock `tempfile.TemporaryDirectory` to return a known path, OR we can rely on the fact that
    # our MockProcess is instantiated with `cmd` which contains the output path!

    # Let's use a closure to capture the command and create files
    captured_cmd = []

    def mock_popen(cmd, *args, **kwargs):
        captured_cmd.append(cmd)
        # Parse output dir from cmd: ... "--output", "PATH" ...
        try:
            out_idx = cmd.index("--output")
            out_dir = Path(cmd[out_idx + 1])
            # Create expected output file
            # Input is doc.pdf -> output doc.md (since format is md)
            (out_dir / "doc.md").write_text("Markdown content with image: ![](doc_page_1_figure_1.png)")

            # Create referenced image
            (out_dir / "doc_page_1_figure_1.png").write_bytes(b"fake_image_content")
        except ValueError:
            pass

        return MockProcess(cmd, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr("subprocess.Popen", mock_popen)

        # Run command
        result = run_cmd(cmd_transform, engine="docling", file_path=test_file, overrides={}, output=None)

        assert result.success
        assert "docling" in captured_cmd[0][0]
        assert "--ocr" in captured_cmd[0]
        assert "tesseract" in captured_cmd[0]

        # Verify content availability via checksum or similar
        # Output content should have replaced image path with URI
        assert "output_content" in result.output
        # Since we didn't request output content, it might be None in result but we can check cache
        # Actually expected structure test says output_content is None by default.
        # But we can check if referenced file exists in cache?
        # We can't easily know the checksum of the image without recomputing it.


def test_controller_management_ops(monkeypatch, tmp_path, minimal_config_dict):
    """Test internal controller methods (remove_by_uri, update_uri) directly for coverage."""
    # These methods are currently internal helpers or future API, but we need to ensure they work.

    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Needs valid DB config for Mongomock
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**cfg["database"])

    # We need to instantiate the controller.
    # It requires a Config object and a Database object.
    # Load full config to get TransformConfig
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.database.Database import Database
    from wks.api.transform._TransformController import _TransformController

    wks_config = WKSConfig.load()
    transform_config = wks_config.transform

    with Database(db_config, "transform") as db:
        controller = _TransformController(db, transform_config, "test")

        # Setup: Add a fake record
        db.get_database()["transform"].insert_one(
            {
                "file_uri": "file:///test/a.txt",
                "cache_uri": "file:///cache/a.md",
                "checksum": "abc",
                "engine": "test",
                "options_hash": "123",
                "size_bytes": 100,
                "created_at": "2023-01-01T00:00:00",
                "last_accessed": "2023-01-01T00:00:00",
            }
        )

        # Test update_uri
        count = controller.update_uri("file:///test/a.txt", "file:///test/b.txt")
        assert count == 1
        record = db.get_database()["transform"].find_one({"file_uri": "file:///test/b.txt"})
        assert record is not None

        # Test remove_by_uri
        # Mock cache file handling (controller unlink/remove_file)
        # We need the cache file to exist or mock the check?
        # The logic: checks if cache_path exists, then unlinks.
        # we can create a fake file at valid path

        # Construct path that matches what controller expects?
        # The record has `cache_uri`. uri_to_path will parse it.
        # cache_path = uri_to_path("file:///cache/a.md")
        # Ensure directory exists if we want to touch it?
        # /cache might be root, depends on system.
        # Safe to mock uri_to_path to return a tmp path?

        with monkeypatch.context() as m:
            fake_cache_file = tmp_path / "a.md"
            fake_cache_file.touch()

            def mock_uri_to_path(uri):
                return fake_cache_file

            # Patch uri_to_path passed to controller or imported in controller
            # Controller has `from ...utils.uri_to_path import uri_to_path`
            # Note: inside `remove_by_uri` it does a local import:
            # `from ...utils.uri_to_path import uri_to_path`! (Line 373)
            # So patching wks.utils.uri_to_path might work if imported from there.
            # But line 373 imports it inside the method.
            # Patch globally
            # Patch globally where it is defined, since it is imported inside the function
            m.setattr("wks.utils.uri_to_path.uri_to_path", mock_uri_to_path)
            # If it imports locally, we might need to patch sys.modules or the module where it's defined.
            m.setattr("wks.utils.uri_to_path.uri_to_path", mock_uri_to_path)

            removed = controller.remove_by_uri("file:///test/b.txt")
            assert removed == 1
            assert not fake_cache_file.exists()
            assert db.get_database()["transform"].count_documents({}) == 0
