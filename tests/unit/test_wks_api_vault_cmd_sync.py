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
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync)

    assert "notes_scanned" in result.output
    assert "links_written" in result.output
    assert "links_deleted" in result.output
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
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
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
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync, path="/nonexistent/file.md")

    assert result.success is False
    assert len(result.output["errors"]) > 0


def test_vault_sync_with_notes(monkeypatch, tmp_path, minimal_config_dict):
    """Vault sync scans notes with links."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Create notes with links
    (vault_dir / "note_A.md").write_text("# Note A\n[[wikilink]]\n[[note_B]]", encoding="utf-8")
    (vault_dir / "note_B.md").write_text("# Note B\n[[note_A]]", encoding="utf-8")
    (vault_dir / "nested").mkdir()
    (vault_dir / "nested" / "note_C.md").write_text("I am nested.", encoding="utf-8")

    result = run_cmd(cmd_sync)

    # Sync should succeed and find notes
    assert result.success is True, f"Sync failed: {result.output.get('errors')}"
    assert result.output["notes_scanned"] >= 3


def test_vault_sync_no_config(monkeypatch, tmp_path):
    """Should fail gracefully if config is missing."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    result = run_cmd(cmd_sync)

    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]
