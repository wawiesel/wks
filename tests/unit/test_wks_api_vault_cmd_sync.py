"""Unit tests for vault cmd_sync."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_sync import cmd_sync

pytestmark = pytest.mark.vault


def test_cmd_sync_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync returns expected output structure."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync)

    assert "notes_scanned" in result.output
    assert "edges_written" in result.output
    assert "edges_deleted" in result.output
    assert "sync_duration_ms" in result.output
    assert "success" in result.output


def test_cmd_sync_empty_vault(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync on empty vault reports zero scanned."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync)

    assert result.output["notes_scanned"] == 0
    assert result.success is True


def test_cmd_sync_nonexistent_path_fails(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync with nonexistent path returns error."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync, path="/nonexistent/file.md")

    assert result.success is False
    assert len(result.output["errors"]) > 0
