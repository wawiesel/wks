"""Unit tests for wks.api.link.cmd_status."""

import json

from tests.unit.conftest import run_cmd
from wks.api.link.cmd_status import cmd_status


def test_cmd_status_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_status returns expected output structure."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(cmd_status)

    assert result.success
    assert "total_links" in result.output
    assert "total_files" in result.output


def test_cmd_status_empty_database(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_status on empty edges database."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(cmd_status)

    assert result.success
    assert result.output["total_links"] == 0
    assert result.output["total_files"] == 0
