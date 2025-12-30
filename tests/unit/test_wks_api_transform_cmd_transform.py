"""Unit tests for transform cmd_transform."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_transform import cmd_transform

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
