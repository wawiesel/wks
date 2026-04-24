from pathlib import Path

from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform._RouteEngineConfig import _RouteEngineConfig, _RouteEngineData
from wks.api.transform.cmd_engine import cmd_engine


def test_cmd_engine_path_not_found(tracked_wks_config):
    """Test error when path does not exist."""
    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(Path("/non/existent")),
        overrides={},
    )
    assert result.success is False
    assert "not found" in result.result or "not found" in str(result.output)


def test_cmd_engine_no_engines(tracked_wks_config, tmp_path):
    """Test error when no engines configured."""
    test_f = tmp_path / "test.txt"
    test_f.touch()

    config = WKSConfig.load()
    config.transform.engines = {}
    config.save()

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert result.success is False
    assert "No engines" in result.result or "not found" in result.result


def test_cmd_engine_success_and_caching(tracked_wks_config, tmp_path):
    """Test successful transform and caching behavior."""
    test_f = tmp_path / "test.txt"
    test_f.write_text("hello", encoding="utf-8")

    res1 = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert res1.success is True
    assert "Transformed" in res1.result
    assert res1.output["cached"] is False
    assert res1.output["checksum"] is not None

    res2 = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert res2.success is True
    assert res2.output["cached"] is True
    assert res2.output["checksum"] == res1.output["checksum"]


def test_cmd_engine_route_engine_text_success(tracked_wks_config, tmp_path):
    test_f = tmp_path / "test.md"
    test_f.write_text("# hello\n", encoding="utf-8")

    config = WKSConfig.load()
    config.transform.engines["ast"] = _EngineConfig(
        type="treesitter",
        data={"language": "auto", "format": "sexp"},
        supported_types=[".py", ".js", ".ts"],
    )
    config.transform.engines["default"] = _RouteEngineConfig(
        type="route",
        data=_RouteEngineData(order=["docling_test", "ast"], passthrough_text=True, reject_binary=True),
    )
    config.transform.default_engine = "default"
    config.save()

    result = run_cmd(
        cmd_engine,
        engine="default",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert result.success is True
    assert result.output["cached"] is False


def test_cmd_engine_route_engine_rejects_binary_without_named_null(tracked_wks_config, tmp_path):
    test_f = tmp_path / "test.bin"
    test_f.write_bytes(b"\x00\x01\x02")

    config = WKSConfig.load()
    config.transform.engines["default"] = _RouteEngineConfig(
        type="route",
        data=_RouteEngineData(order=["docling_test"], passthrough_text=True, reject_binary=True),
    )
    config.transform.default_engine = "default"
    config.save()

    result = run_cmd(
        cmd_engine,
        engine="default",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert result.success is False
    assert "no transform available for binary file" in result.result.lower()


def test_cmd_engine_rejects_unsupported_supported_types(tracked_wks_config, tmp_path):
    test_f = tmp_path / "test.txt"
    test_f.write_text("hello", encoding="utf-8")

    config = WKSConfig.load()
    config.transform.engines["doc_only"] = _EngineConfig(
        type="docling",
        data={
            "ocr": False,
            "ocr_languages": ["eng"],
            "image_export_mode": "embedded",
            "pipeline": "standard",
            "timeout_secs": 30,
            "to": "md",
        },
        supported_types=[".pdf", ".docx"],
    )
    config.save()

    result = run_cmd(
        cmd_engine,
        engine="doc_only",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert result.success is False
    assert "unsupported file type" in result.result.lower()


def test_cmd_engine_fatal_error(tracked_wks_config, tmp_path):
    """Test fatal error during transform."""
    test_f = tmp_path / "test.txt"
    test_f.touch()

    result = run_cmd(
        cmd_engine,
        engine="textpass",
        uri=URI.from_path(tmp_path / "nonexistent.txt"),
        overrides={},
    )
    assert result.success is False


def test_cache_eviction_integration(tracked_wks_config, tmp_path):
    """Test cache eviction by setting small limit and checking behavior."""
    config = WKSConfig.load()
    config.transform.cache.max_size_bytes = 200
    config.save()

    f1 = tmp_path / "f1.txt"
    f1.write_text("a" * 150)

    res1 = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f1), overrides={})
    assert res1.success is True
    assert res1.output["cached"] is False

    f2 = tmp_path / "f2.txt"
    f2.write_text("b" * 150)

    res2 = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f2), overrides={})
    assert res2.success is True

    res1_again = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f1), overrides={})
    assert res1_again.success is True
    assert res1_again.output["cached"] is False

    res2_again = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f2), overrides={})
    assert res2_again.success is True
    assert res2_again.output["cached"] is False


def test_cache_permission_error(tracked_wks_config, tmp_path):
    """Test handling of permission error in cache directory."""

    config = WKSConfig.load()
    cache_dir = tmp_path / "readonly_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    try:
        cache_dir.chmod(0o500)  # Read/Execute, No Write

        f1 = tmp_path / "f1.txt"
        f1.write_text("content")

        res = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(f1), overrides={})
        assert res.success is False
        assert "Permission" in str(res.output) or "Access" in str(res.output) or "ReadOnly" in str(res.output)

    finally:
        cache_dir.chmod(0o700)
