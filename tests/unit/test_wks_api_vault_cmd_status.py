"""Unit tests for vault cmd_status."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_status import cmd_status

pytestmark = pytest.mark.vault


def test_cmd_status_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_status returns expected output structure."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create vault directory
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_status)

    # Should have expected output keys
    assert "total_links" in result.output
    assert "ok_links" in result.output
    assert "broken_links" in result.output
    assert "issues" in result.output
    assert "last_sync" in result.output
    assert "success" in result.output


def test_cmd_status_empty_vault(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_status on empty vault returns zero counts."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_status)

    assert result.output["total_links"] == 0
    assert result.output["ok_links"] == 0
    assert result.output["broken_links"] == 0
