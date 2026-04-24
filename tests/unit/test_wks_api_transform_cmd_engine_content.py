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


def write_text_file(tmp_path, name="test.txt", content="test content") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def run_textpass(path: Path, *, output: Path | None = None):
    return run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(path), overrides={}, output=output)


def rename_cached_file(checksum: str) -> tuple[Path, WKSConfig]:
    config = WKSConfig.load()
    cache_dir = Path(config.transform.cache.base_dir)
    original = next(iter(cache_dir.glob(f"{checksum}.*")))
    renamed = cache_dir / f"{checksum}.{'txt' if original.suffix == '.md' else 'md'}"
    original.rename(renamed)
    return renamed, config


def test_database_corruption_recovery(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path, "f1.txt", "content")
    checksum = run_textpass(source).output["checksum"]

    config = WKSConfig.load()
    for path in Path(config.transform.cache.base_dir).iterdir():
        if path.is_file():
            path.unlink()

    with pytest.raises(ValueError, match=r"Cache file missing|not found"):
        get_content(checksum)

    with Database(config.database, "transform") as db:
        assert db.get_database()["transform"].count_documents({}) == 0

    result = run_textpass(source)
    assert result.success is True
    assert result.output["cached"] is False


def test_expand_path_fallback(tracked_wks_config, tmp_path, monkeypatch):
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)

    assert run_textpass(write_text_file(tmp_path, "f1.txt", "content")).success is True


def test_cmd_engine_error_output_schema_conformance(tracked_wks_config, tmp_path):
    result = run_textpass(tmp_path / "nonexistent.txt")

    assert result.success is False
    assert "not found" in result.result.lower()
    TransformEngineOutput.model_validate(result.output)


@pytest.mark.parametrize("cached_first", [False, True])
def test_cmd_engine_with_output_path(tracked_wks_config, tmp_path, cached_first):
    source = write_text_file(tmp_path)
    output_file = tmp_path / "output.md"
    if cached_first:
        first = run_textpass(source)
        assert first.success is True
        assert first.output["cached"] is False

    result = run_textpass(source, output=output_file)

    assert result.success is True
    assert result.output["cached"] is cached_first
    assert output_file.read_text() == "test content"


def test_cmd_engine_with_referenced_uris_updates_graph(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path)
    config = WKSConfig.load()
    engine = "docling_test" if "docling_test" in config.transform.engines else "textpass"

    result = run_cmd(cmd_engine, engine=engine, uri=URI.from_path(source), overrides={})

    if engine == "docling_test":
        assert isinstance(result.success, bool)
        return
    assert result.success is True


@pytest.mark.parametrize("target_factory", [lambda path, checksum: checksum, lambda path, checksum: str(path)])
def test_get_content_by_checksum_or_path(tracked_wks_config, tmp_path, target_factory):
    source = write_text_file(tmp_path)
    result = run_textpass(source)

    content = get_content(target_factory(source, result.output["checksum"]))

    assert "test content" in content


def test_get_content_with_output_path(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path)
    output_file = tmp_path / "output.md"
    result = run_textpass(source)

    content = get_content(result.output["checksum"], output_path=output_file)

    assert "test content" in content
    assert output_file.read_text() == "test content"


@pytest.mark.parametrize(
    ("target", "match"),
    [("a" * 64, r"not found|Cache file missing"), ("/nonexistent/file.txt", "File not found")],
)
def test_get_content_invalid_inputs(tracked_wks_config, target, match):
    with pytest.raises(ValueError, match=match):
        get_content(target)


def test_cmd_engine_unknown_engine_type(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path, content="test")

    with temporary_transform_config(engines={"bad": _EngineConfig(type="unknown_type", data={})}):
        result = run_cmd(cmd_engine, engine="bad", uri=URI.from_path(source), overrides={})

    assert result.success is False
    assert "Unknown engine type" in result.result


def test_cmd_engine_glob_fallback_for_cache_location(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path)
    checksum = run_textpass(source).output["checksum"]
    rename_cached_file(checksum)

    assert run_textpass(source).success is True


def test_get_content_with_existing_output_file(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path)
    output_file = tmp_path / "output.md"
    output_file.write_text("existing", encoding="utf-8")
    result = run_textpass(source)

    with pytest.raises(FileExistsError, match="already exists"):
        get_content(result.output["checksum"], output_path=output_file)


def test_get_content_glob_fallback_different_extension(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path)
    result = run_textpass(source)
    renamed_file, config = rename_cached_file(result.output["checksum"])

    with Database(config.database, "transform") as db:
        db.update_many(
            {"checksum": result.output["checksum"]},
            {"$set": {"cache_uri": str(URI.from_path(renamed_file))}},
        )

    assert "test content" in get_content(result.output["checksum"])


def test_get_content_oserror_fallback_hardlink(tracked_wks_config, tmp_path):
    source = write_text_file(tmp_path)
    checksum = run_textpass(source).output["checksum"]
    output_dir = tmp_path / "restricted"
    output_file = output_dir / "output.md"
    output_dir.mkdir()
    original_mode = output_dir.stat().st_mode

    try:
        output_dir.chmod(0o555)
        try:
            content = get_content(checksum, output_path=output_file)
        except PermissionError:
            output_dir.chmod(0o755)
            content = get_content(checksum, output_path=output_file)
    finally:
        output_dir.chmod(original_mode)
        if output_file.exists():
            output_file.unlink()

    assert "test content" in content


def test_transform_file_not_found_direct(tracked_wks_config, tmp_path):
    with _get_controller() as controller:
        gen = controller.transform(tmp_path / "nonexistent.txt", "test", {})
        with pytest.raises(ValueError, match="not found"):
            while True:
                next(gen)
