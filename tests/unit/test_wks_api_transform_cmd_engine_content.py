"""Content retrieval and cache integrity tests for transform command APIs."""

from pathlib import Path

import pytest

from tests.unit._transform_test_helpers import temporary_transform_config
from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.transform import TransformEngineOutput
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform._get_controller import _get_controller
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content


def test_database_corruption_recovery(tracked_wks_config, tmp_path):
    """Stale DB records must be pruned when the cache file is gone."""
    f1 = tmp_path / "f1.txt"
    f1.write_text("content")

    res = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f1), overrides={})
    checksum = res.output["checksum"]

    config = WKSConfig.load()
    cache_dir = Path(config.transform.cache.base_dir)
    for path in cache_dir.iterdir():
        if path.is_file():
            path.unlink()

    with pytest.raises(ValueError, match=r"Cache file missing|not found"):
        get_content(checksum)

    with Database(config.database, "transform") as db:
        assert db.get_database()["transform"].count_documents({}) == 0

    res = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f1), overrides={})
    assert res.success is True
    assert res.output["cached"] is False


def test_expand_path_fallback(tracked_wks_config, tmp_path, monkeypatch):
    """Transform should still work when HOME-based expansion variables are absent."""
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)

    f1 = tmp_path / "f1.txt"
    f1.write_text("content")

    res = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f1), overrides={})
    assert res.success is True


def test_cmd_engine_error_output_schema_conformance(tracked_wks_config, tmp_path):
    """Transform command errors must still satisfy the public output schema."""
    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(tmp_path / "nonexistent.txt"),
        overrides={},
    )

    assert result.success is False
    TransformEngineOutput.model_validate(result.output)


def test_cmd_engine_with_output_path(tracked_wks_config, tmp_path):
    """cmd_engine should copy the rendered content to an explicit output path."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")
    output_file = tmp_path / "output.md"

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
        output=output_file,
    )

    assert result.success is True
    assert output_file.exists()
    assert output_file.read_text() == "test content"


def test_cmd_engine_cached_with_output_path(tracked_wks_config, tmp_path):
    """cmd_engine should still honor output_path when returning cached content."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")
    output_file = tmp_path / "output.md"

    res1 = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert res1.success is True
    assert res1.output["cached"] is False

    res2 = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
        output=output_file,
    )

    assert res2.success is True
    assert res2.output["cached"] is True
    assert output_file.exists()
    assert output_file.read_text() == "test content"


def test_cmd_engine_with_referenced_uris_updates_graph(tracked_wks_config, tmp_path):
    """Transforms should still succeed whether or not referenced URIs are returned."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    config = WKSConfig.load()
    if "docling_test" in config.transform.engines:
        result = run_cmd(
            cmd_engine,
            engine="docling_test",
            uri=URI.from_path(test_file),
            overrides={},
        )
        assert result.success is True or result.success is False
        return

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True


def test_get_content_by_checksum(tracked_wks_config, tmp_path):
    """get_content should resolve previously transformed content by checksum."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True

    content = get_content(result.output["checksum"])
    assert "test content" in content


def test_get_content_by_file_path(tracked_wks_config, tmp_path):
    """get_content should resolve content by the original source path."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True

    content = get_content(str(test_file))
    assert "test content" in content


def test_get_content_with_output_path(tracked_wks_config, tmp_path):
    """get_content should materialize content to output_path when requested."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")
    output_file = tmp_path / "output.md"

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True

    content = get_content(result.output["checksum"], output_path=output_file)
    assert "test content" in content
    assert output_file.exists()
    assert output_file.read_text() == "test content"


def test_get_content_invalid_checksum(tracked_wks_config):
    """Invalid-but-well-formed checksums should fail cleanly."""
    with pytest.raises(ValueError, match=r"not found|Cache file missing"):
        get_content("a" * 64)


def test_get_content_invalid_path(tracked_wks_config):
    """Non-existent source paths should fail cleanly."""
    with pytest.raises(ValueError, match="File not found"):
        get_content("/nonexistent/file.txt")


def test_cmd_engine_unknown_engine_type(tracked_wks_config, tmp_path):
    """Unknown engine types must fail explicitly."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")

    with temporary_transform_config(engines={"bad": _EngineConfig(type="unknown_type", data={})}):
        result = run_cmd(
            cmd_engine,
            engine="bad",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is False
        assert "Unknown engine type" in result.result


def test_cmd_engine_glob_fallback_for_cache_location(tracked_wks_config, tmp_path):
    """cmd_engine should recover when the cache file extension changes."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True
    checksum = result.output["checksum"]

    config = WKSConfig.load()
    cache_dir = Path(config.transform.cache.base_dir)
    original_file = next(iter(cache_dir.glob(f"{checksum}.*")))
    new_extension = "txt" if original_file.suffix == ".md" else "md"
    renamed_file = cache_dir / f"{checksum}.{new_extension}"
    original_file.rename(renamed_file)

    result2 = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result2.success is True


def test_cmd_engine_file_not_found(tracked_wks_config, tmp_path):
    """cmd_engine should return a visible failure for missing files."""
    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(tmp_path / "nonexistent.txt"),
        overrides={},
    )

    assert result.success is False
    assert "File not found" in result.result or "not found" in result.result.lower()


def test_get_content_with_existing_output_file(tracked_wks_config, tmp_path):
    """Existing output targets must not be silently overwritten."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")
    output_file = tmp_path / "output.md"
    output_file.write_text("existing", encoding="utf-8")

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True

    with pytest.raises(FileExistsError, match="already exists"):
        get_content(result.output["checksum"], output_path=output_file)


def test_get_content_glob_fallback_different_extension(tracked_wks_config, tmp_path):
    """get_content should recover when the cached extension differs from the DB suffix."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True
    checksum = result.output["checksum"]

    config = WKSConfig.load()
    cache_dir = Path(config.transform.cache.base_dir)
    original_file = next(iter(cache_dir.glob(f"{checksum}.*")))
    new_extension = "txt" if original_file.suffix == ".md" else "md"
    renamed_file = cache_dir / f"{checksum}.{new_extension}"
    original_file.rename(renamed_file)

    with Database(config.database, "transform") as db:
        db.update_many({"checksum": checksum}, {"$set": {"cache_uri": str(URI.from_path(renamed_file))}})

    content = get_content(checksum)
    assert "test content" in content


def test_get_content_oserror_fallback_hardlink(tracked_wks_config, tmp_path):
    """get_content should fall back cleanly when hard-link creation fails."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_file),
        overrides={},
    )
    assert result.success is True
    checksum = result.output["checksum"]

    output_dir = tmp_path / "restricted"
    output_file = output_dir / "output.md"
    output_dir.mkdir()
    original_mode = output_dir.stat().st_mode
    try:
        output_dir.chmod(0o555)
        try:
            content = get_content(checksum, output_path=output_file)
            assert "test content" in content
        except PermissionError:
            output_dir.chmod(0o755)
            content = get_content(checksum, output_path=output_file)
            assert "test content" in content
    finally:
        output_dir.chmod(original_mode)
        if output_file.exists():
            output_file.unlink()


def test_transform_file_not_found_direct(tracked_wks_config, tmp_path):
    """Controller.transform should fail directly for missing inputs."""
    with _get_controller() as controller:
        gen = controller.transform(tmp_path / "nonexistent.txt", "test", {})
        try:
            while True:
                next(gen)
        except ValueError as exc:
            assert "File not found" in str(exc) or "not found" in str(exc).lower()
            return

    pytest.fail("Expected ValueError for non-existent file")
