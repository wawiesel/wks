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
    cfg["vault"]["type"] = "obsidian"
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
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
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
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check, path="/nonexistent/file.md")

    assert result.success is False
    assert len(result.output["errors"]) > 0


def test_cmd_check_config_failure(monkeypatch):
    """cmd_check handles config load failure gracefully."""

    def mock_load():
        raise RuntimeError("Config Error")

    monkeypatch.setattr("wks.api.config.WKSConfig.WKSConfig.load", mock_load)

    result = run_cmd(cmd_check)
    assert result.success is False
    assert "Config Error" in result.output["errors"][0]


def test_cmd_check_vault_init_failure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check handles vault init failure gracefully."""
    # Setup valid config to bypass config load
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_config_dict
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = "/tmp"
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Mock Vault init failure
    def mock_enter(*args, **kwargs):
        raise RuntimeError("Vault Init Error")

    monkeypatch.setattr("wks.api.vault.Vault.Vault.__enter__", mock_enter)

    result = run_cmd(cmd_check)
    assert result.success is False
    assert "Vault Init Error" in result.output["errors"][0]
