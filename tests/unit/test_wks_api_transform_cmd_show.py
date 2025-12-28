"""Unit tests for transform cmd_show."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_show import cmd_show
from wks.api.transform.cmd_transform import cmd_transform

pytestmark = pytest.mark.transform


def test_cmd_show_returns_record(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_show returns transform record details."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # First, transform a file to create a record
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    transform_result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=None)
    assert transform_result.success
    checksum = transform_result.output["checksum"]

    # Now show the record
    show_result = run_cmd(cmd_show, checksum=checksum, content=False)

    assert show_result.success
    assert "checksum" in show_result.output or "file_uri" in show_result.output


def test_cmd_show_with_content(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_show with content=True returns file content."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    transform_result = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={}, output=None)
    assert transform_result.success
    checksum = transform_result.output["checksum"]

    show_result = run_cmd(cmd_show, checksum=checksum, content=True)

    assert show_result.success
    assert "content" in show_result.output
    assert "Transformed:" in show_result.output["content"]


def test_cmd_show_not_found(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_show fails for nonexistent checksum."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_show, checksum="nonexistent123", content=False)

    assert not result.success
