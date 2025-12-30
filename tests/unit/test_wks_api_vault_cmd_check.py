"""Unit tests for vault cmd_check."""

import json
import platform

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_check import cmd_check

pytestmark = pytest.mark.vault


def test_cmd_check_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check returns expected output structure."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
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
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
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
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check, path="/nonexistent/file.md")

    assert result.success is False
    assert len(result.output["errors"]) > 0


def test_cmd_check_config_failure(monkeypatch, tmp_path):
    """cmd_check handles config load failure gracefully."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    # No config file created

    result = run_cmd(cmd_check)
    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_cmd_check_vault_init_failure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check handles vault init failure gracefully."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

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


def test_scanner_rewrites_file_urls_via_check(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check should trigger file:// URL rewriting and symlink creation."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    ext_file = (tmp_path / "external.txt").resolve()
    ext_file.write_text("external content", encoding="utf-8")
    ext_uri = ext_file.as_uri()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    note = vault_dir / "note.md"
    note.write_text(f"Check this: [external]({ext_uri})", encoding="utf-8")

    result = run_cmd(cmd_check)
    assert result.success

    content = note.read_text(encoding="utf-8")
    assert "[[_links/" in content

    machine = platform.node().split(".")[0]
    assert (vault_dir / "_links" / machine).exists()


def test_scanner_handles_missing_file_url_via_check(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check handles missing file URLs in scanner."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    bad_uri = "file:///non/existent/path/file.txt"
    note = vault_dir / "note.md"
    note.write_text(f"[bad]({bad_uri})", encoding="utf-8")

    result = run_cmd(cmd_check)
    assert result.success is False
    assert any("non-existent path" in err for err in result.output["errors"])


def test_resolve_attachment_via_check(monkeypatch, tmp_path, minimal_config_dict):
    """Test resolution of vault attachments via cmd_check."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    (vault_dir / "_img.png").write_text("data", encoding="utf-8")
    (vault_dir / "note.md").write_text("[[_img.png]]", encoding="utf-8")

    result = run_cmd(cmd_check)
    assert result.success
    assert result.output["links_checked"] >= 1
