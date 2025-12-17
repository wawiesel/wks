"""Unit tests for vault cmd_check."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_check import cmd_check

pytestmark = pytest.mark.vault


def test_cmd_check_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check returns expected output structure."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check)

    assert "notes_checked" in result.output
    assert "links_checked" in result.output
    assert "broken_count" in result.output
    assert "is_valid" in result.output
    assert "success" in result.output


def test_cmd_check_empty_vault_is_valid(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check on empty vault reports as valid."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check)

    assert result.output["is_valid"] is True
    assert result.output["broken_count"] == 0
    assert result.success is True


def test_cmd_check_nonexistent_path_fails(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check with nonexistent path returns error."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check, path="/nonexistent/file.md")

    assert result.success is False
    assert len(result.output["errors"]) > 0
